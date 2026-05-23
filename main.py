from fastapi import FastAPI, Depends, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import Base, engine, SessionLocal
from models import FiscalRisk, RNFiscalClient
from odoo_saas import router as odoo_saas_router

import csv
import io
from datetime import datetime


Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="RN Fiscal Risk API",
    version="1.0.0",
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def normalize_rfc(value):
    return (value or "").strip().upper()


def is_valid_rfc(rfc):
    if not rfc:
        return False

    invalid_rfcs = {
        "XXXXXXXXXXXX",
        "XAXX010101000",
        "XEXX010101000",
    }

    if rfc in invalid_rfcs:
        return False

    if len(rfc) not in (12, 13):
        return False

    return True


def parse_date(value):
    if not value:
        return None

    value = value.strip()

    formats = [
        "%d/%m/%Y",
        "%Y-%m-%d",
        "%d-%m-%Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date()
        except Exception:
            continue

    return None


def classify_risk(situation):
    situation = (situation or "").strip().lower()

    if "definitivo" in situation:
        return "red", "69-B Definitivo"

    if "presunto" in situation:
        return "yellow", "69-B Presunto"

    if "desvirtuado" in situation:
        return "gray", "69-B Desvirtuado"

    if "sentencia" in situation or "favorable" in situation:
        return "gray", "69-B Sentencia Favorable"

    return "yellow", "69-B"


@app.get("/")
def root():
    return {
        "message": "RN Fiscal Risk API running",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
    }


class OnboardingRequest(BaseModel):
    company_name: str | None = None
    odoo_company_id: int | None = None
    odoo_company_name: str | None = None
    company_rfc: str
    sat_ciec: str
    odoo_url: str
    odoo_database: str | None = None
    odoo_login: str
    odoo_password: str
    alert_email: str | None = None
    auto_validate_risk: bool | None = False
    source: str | None = "odoo_module"


@app.post("/api/v1/onboarding/register")
def register_onboarding(
    data: OnboardingRequest,
    db: Session = Depends(get_db),
):
    clean_rfc = normalize_rfc(data.company_rfc)
    company_key = data.odoo_company_id or "NOCO"
    customer_id = f"RNFS-{clean_rfc}-{company_key}"

    existing = (
        db.query(RNFiscalClient)
        .filter(RNFiscalClient.customer_id == customer_id)
        .first()
    )

    if existing:
        existing.company_name = data.company_name
        existing.company_rfc = clean_rfc
        existing.sat_ciec = data.sat_ciec
        existing.odoo_url = data.odoo_url
        existing.odoo_database = data.odoo_database
        existing.odoo_login = data.odoo_login
        existing.odoo_password = data.odoo_password
        existing.odoo_company_id = data.odoo_company_id
        existing.odoo_company_name = data.odoo_company_name
        existing.alert_email = data.alert_email
        existing.auto_validate_risk = bool(data.auto_validate_risk)
        existing.source = data.source
        existing.onboarding_status = "pending"
        existing.onboarding_message = (
            "Cliente actualizado correctamente. "
            "Pendiente de activación automática."
        )

        db.commit()
        db.refresh(existing)

        return {
            "status": existing.onboarding_status,
            "customer_id": existing.customer_id,
            "message": existing.onboarding_message,
        }

    client = RNFiscalClient(
        customer_id=customer_id,
        company_name=data.company_name,
        company_rfc=clean_rfc,
        sat_ciec=data.sat_ciec,
        odoo_url=data.odoo_url,
        odoo_database=data.odoo_database,
        odoo_login=data.odoo_login,
        odoo_password=data.odoo_password,
        odoo_company_id=data.odoo_company_id,
        odoo_company_name=data.odoo_company_name,
        alert_email=data.alert_email,
        auto_validate_risk=bool(data.auto_validate_risk),
        source=data.source,
        onboarding_status="pending",
        onboarding_message=(
            "Tu RFC quedó registrado correctamente. "
            "La sincronización automática iniciará cuando "
            "el servicio sea activado."
        ),
    )

    db.add(client)
    db.commit()
    db.refresh(client)

    return {
        "status": client.onboarding_status,
        "customer_id": client.customer_id,
        "message": client.onboarding_message,
    }

@app.post("/api/v1/xml/upload")
async def upload_xml(
    customer_id: str = Form(...),
    file: UploadFile = File(...),
):
    import xml.etree.ElementTree as ET

    content = await file.read()

    try:
        root = ET.fromstring(content)
    except Exception as e:
        return {
            "success": False,
            "error": f"Invalid XML: {str(e)}",
        }

    namespaces = {
        "cfdi": "http://www.sat.gob.mx/cfd/4",
        "tfd": "http://www.sat.gob.mx/TimbreFiscalDigital",
    }

    comprobante = root
    emisor = root.find("cfdi:Emisor", namespaces)
    receptor = root.find("cfdi:Receptor", namespaces)
    timbre = root.find(".//tfd:TimbreFiscalDigital", namespaces)

    uuid = timbre.attrib.get("UUID") if timbre is not None else None

    return {
        "success": True,
        "customer_id": customer_id,
        "filename": file.filename,
        "uuid": uuid,
        "supplier_rfc": emisor.attrib.get("Rfc") if emisor is not None else None,
        "supplier_name": emisor.attrib.get("Nombre") if emisor is not None else None,
        "receiver_rfc": receptor.attrib.get("Rfc") if receptor is not None else None,
        "receiver_name": receptor.attrib.get("Nombre") if receptor is not None else None,
        "folio": comprobante.attrib.get("Folio"),
        "serie": comprobante.attrib.get("Serie"),
        "fecha": comprobante.attrib.get("Fecha"),
        "subtotal": comprobante.attrib.get("SubTotal"),
        "total": comprobante.attrib.get("Total"),
        "currency": comprobante.attrib.get("Moneda"),
        "message": "XML received and parsed successfully.",
    }

app.include_router(odoo_saas_router)