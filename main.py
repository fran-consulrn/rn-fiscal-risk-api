from fastapi import FastAPI, Depends, UploadFile, File
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
    version="1.0.0"
)

app.include_router(odoo_saas_router)


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
        "message": "RN Fiscal Risk API running"
    }


@app.get("/health")
def health():
    return {
        "status": "ok"
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