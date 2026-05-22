from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.client import Client

router = APIRouter()


class OnboardingRequest(BaseModel):
    company_rfc: str
    sat_ciec: str
    odoo_url: str
    odoo_login: str
    odoo_password: str
    alert_email: str | None = None


@router.post("/api/v1/onboarding/register")
async def register_client(data: OnboardingRequest):

    db: Session = SessionLocal()

    existing = (
        db.query(Client)
        .filter(Client.company_rfc == data.company_rfc)
        .first()
    )

    if existing:
        return {
            "status": "existing",
            "customer_id": existing.id,
            "message": "Client already exists."
        }

    client = Client(
        company_rfc=data.company_rfc,
        sat_ciec=data.sat_ciec,
        odoo_url=data.odoo_url,
        odoo_login=data.odoo_login,
        odoo_password=data.odoo_password,
        alert_email=data.alert_email,
        onboarding_status="pending",
    )

    db.add(client)
    db.commit()
    db.refresh(client)

    return {
        "status": "success",
        "customer_id": client.id,
        "message": "Client onboarded successfully."
    }