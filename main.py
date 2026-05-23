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


# Onboarding endpoint and request model
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


@app.get("/api/v1/risk/{rfc}")
def get_risk(rfc: str, db: Session = Depends(get_db)):
    clean_rfc = normalize_rfc(rfc)

    risk = db.query(FiscalRisk).filter(FiscalRisk.rfc == clean_rfc).first()

    if not risk:
        return {
            "found": False
        }

    return {
        "found": True,
        "rfc": risk.rfc,
        "name": risk.name,
        "risk_level": risk.risk_level,
        "list_type": risk.list_type,
        "situation": risk.situation,
        "source": risk.source,
        "publication_date": str(risk.publication_date) if risk.publication_date else None,
        "message": risk.message,
    }


@app.post("/api/v1/risk/demo-seed")
def demo_seed(db: Session = Depends(get_db)):
    existing = db.query(FiscalRisk).filter(FiscalRisk.rfc == "XAXX010101000").first()

    if existing:
        return {
            "message": "Demo RFC already exists"
        }

    risk = FiscalRisk(
        rfc="XAXX010101000",
        name="Proveedor Demo Riesgoso",
        risk_level="red",
        list_type="69-B Definitivo",
        situation="Definitivo",
        source="SAT",
        message="RFC encontrado en lista SAT 69-B Definitivo."
    )

    db.add(risk)
    db.commit()

    return {
        "message": "Demo RFC created"
    }


@app.post("/api/v1/risk/import-csv")
async def import_risk_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()

    text = content.decode("utf-8-sig", errors="ignore")
    lines = text.splitlines()

    header_index = 0

    for index, line in enumerate(lines):
        columns = [col.strip() for col in line.split(",")]

        if "RFC" in columns:
            header_index = index
            break

    reader = csv.DictReader(io.StringIO("\n".join(lines[header_index:])))

    created = 0
    updated = 0
    skipped = 0

    seen_rfcs = set()

    for row in reader:

        rfc = normalize_rfc(
            row.get("RFC") or
            row.get("rfc") or
            row.get("RFC ") or
            row.get("R.F.C.")
        )

        if not is_valid_rfc(rfc):
            skipped += 1
            continue
            
        if rfc in seen_rfcs:
            skipped += 1
            continue
        
        seen_rfcs.add(rfc)

        name = (
            row.get("Nombre del Contribuyente") or
            row.get("Nombre") or
            row.get("Razón Social") or
            row.get("Razon Social") or
            ""
        ).strip()

        situation = (
            row.get("Situación del contribuyente") or
            row.get("Situacion del contribuyente") or
            row.get("Situación") or
            row.get("Situacion") or
            "Presunto"
        ).strip()

        publication_date = parse_date(
            row.get("Fecha de publicación página SAT presuntos") or
            row.get("Fecha publicación SAT") or
            row.get("Fecha de publicación") or
            row.get("Fecha")
        )

        risk_level, list_type = classify_risk(situation)

        message = (
            f"RFC encontrado en listado SAT {list_type}. "
            f"Situación: {situation}."
        )

        existing = db.query(FiscalRisk).filter(
            FiscalRisk.rfc == rfc
        ).first()

        if existing:
            existing.name = name
            existing.risk_level = risk_level
            existing.list_type = list_type
            existing.situation = situation
            existing.source = "SAT 69-B"
            existing.publication_date = publication_date
            existing.message = message

            updated += 1

        else:
            risk = FiscalRisk(
                rfc=rfc,
                name=name,
                risk_level=risk_level,
                list_type=list_type,
                situation=situation,
                source="SAT 69-B",
                publication_date=publication_date,
                message=message,
            )

            db.add(risk)

            created += 1

    db.commit()

    return {
        "message": "CSV imported",
        "created": created,
        "updated": updated,
        "skipped": skipped,
    }
