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
    database: str | None = None
    license_key: str | None = None
    alert_email: str | None = None


@router.post("/api/v1/onboarding/register")
async def register_client(data: OnboardingRequest):

    db: Session = SessionLocal()

    try:

        existing = (
            db.query(Client)
            .filter(Client.company_rfc == data.company_rfc)
            .first()
        )

        if existing:

            existing.sat_ciec = data.sat_ciec
            existing.odoo_url = data.odoo_url
            existing.odoo_login = data.odoo_login
            existing.odoo_password = data.odoo_password
            existing.alert_email = data.alert_email
            existing.database = data.database
            existing.license_key = (
                data.license_key
                or existing.license_key
            )

            existing.onboarding_status = "active"

            if not existing.subscription_plan:
                existing.subscription_plan = "starter"

            existing.subscription_active = True

            db.commit()
            db.refresh(existing)

            return {
                "status": "existing",
                "active": existing.subscription_active,
                "plan": existing.subscription_plan,
                "customer_id": str(existing.id),
                "license_key": existing.license_key,
                "message": (
                    "Client subscription refreshed successfully."
                ),
            }

        client = Client(
            company_rfc=data.company_rfc,
            sat_ciec=data.sat_ciec,
            odoo_url=data.odoo_url,
            odoo_login=data.odoo_login,
            odoo_password=data.odoo_password,
            alert_email=data.alert_email,
            database=data.database,
            license_key=data.license_key,
            onboarding_status="active",
            subscription_active=True,
            subscription_plan="starter",
        )

        db.add(client)
        db.commit()
        db.refresh(client)

        return {
            "status": "success",
            "active": client.subscription_active,
            "plan": client.subscription_plan,
            "customer_id": str(client.id),
            "license_key": client.license_key,
            "message": (
                "Client onboarded and subscription "
                "activated successfully."
            ),
        }

    finally:

        db.close()