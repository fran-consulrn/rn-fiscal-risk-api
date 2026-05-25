from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import SessionLocal
from models import RNFiscalClient, RNFiscalXMLDocument


router = APIRouter()


class ManualSyncRequest(BaseModel):
    customer_id: str
    limit: int = 25


@router.post("/api/v1/sat/manual-sync")
def manual_sync_from_odoo(data: ManualSyncRequest):
    db: Session = SessionLocal()

    try:
        client = (
            db.query(RNFiscalClient)
            .filter(RNFiscalClient.customer_id == data.customer_id)
            .first()
        )

        if not client:
            return {
                "success": False,
                "error": "Client not found",
            }

        onboarding_status = getattr(
            client,
            "onboarding_status",
            "active",
        )

        if onboarding_status not in ("active", "pending"):
            return {
                "success": False,
                "error": "Subscription inactive",
            }

        documents = (
            db.query(RNFiscalXMLDocument)
            .filter(RNFiscalXMLDocument.customer_id == data.customer_id)
            .filter(RNFiscalXMLDocument.status != "synced")
            .order_by(RNFiscalXMLDocument.created_at.asc())
            .limit(data.limit)
            .all()
        )

        if not documents:
            return {
                "success": True,
                "message": "No pending XML documents found to sync",
                "customer_id": client.customer_id,
                "company_rfc": client.company_rfc,
                "subscription_plan": getattr(
                    client,
                    "subscription_plan",
                    "starter",
                ),
                "limit": data.limit,
                "scanned": 0,
                "imported": 0,
                "skipped_existing": 0,
                "errors": 0,
                "results": [],
            }

        imported = 0
        errors = 0
        results = []

        for document in documents:
            try:
                # Local import avoids an external HTTP call back into the same Render service.
                from main import send_xml_to_odoo

                result = send_xml_to_odoo(
                    xml_id=document.id,
                    db=db,
                )

                if result.get("success"):
                    imported += 1
                else:
                    errors += 1

                results.append(result)

            except Exception as e:
                errors += 1
                results.append({
                    "success": False,
                    "xml_id": document.id,
                    "error": str(e),
                })

        return {
            "success": errors == 0,
            "message": "Manual sync completed",
            "customer_id": client.customer_id,
            "company_rfc": client.company_rfc,
            "subscription_plan": getattr(
                client,
                "subscription_plan",
                "starter",
            ),
            "limit": data.limit,
            "scanned": len(documents),
            "imported": imported,
            "skipped_existing": 0,
            "errors": errors,
            "results": results,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }

    finally:
        db.close()