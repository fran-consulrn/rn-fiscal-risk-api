from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import SessionLocal
from models import FiscalRisk

import xmlrpc.client
import xml.etree.ElementTree as ET

router = APIRouter()


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

@router.get("/api/v1/odoo/test-connection")
def test_odoo_connection():
    odoo_url = "https://apisat.odoo.com"
    db = "apisat"
    login = "fran@consultorarn.com"
    password = "Maximo.2017"

    try:
        common = xmlrpc.client.ServerProxy(f"{odoo_url}/xmlrpc/2/common")

        uid = common.authenticate(
            db,
            login,
            password,
            {}
        )

        if not uid:
            return {
                "success": False,
                "error": "Authentication failed"
            }

        return {
            "success": True,
            "uid": uid,
            "message": "Odoo connection successful"
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/api/v1/odoo/vendor-bills")
def get_vendor_bills():
    odoo_url = "https://apisat.odoo.com"
    db = "apisat"
    login = "fran@consultorarn.com"
    password = "Maximo.2017"

    try:
        common = xmlrpc.client.ServerProxy(
            f"{odoo_url}/xmlrpc/2/common"
        )

        uid = common.authenticate(
            db,
            login,
            password,
            {}
        )

        if not uid:
            return {
                "success": False,
                "error": "Authentication failed"
            }

        models = xmlrpc.client.ServerProxy(
            f"{odoo_url}/xmlrpc/2/object"
        )

        bills = models.execute_kw(
            db,
            uid,
            password,
            "account.move",
            "search_read",
            [[
                ["move_type", "in", ["in_invoice", "in_refund"]]
            ]],
            {
                "fields": [
                    "name",
                    "ref",
                    "invoice_date",
                    "amount_total",
                    "state"
                ],
                "limit": 10,
                "order": "id desc"
            }
        )

        return {
            "success": True,
            "count": len(bills),
            "bills": bills
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/api/v1/odoo/test-message")
def test_odoo_message():
    odoo_url = "https://apisat.odoo.com"
    db = "apisat"
    login = "fran@consultorarn.com"
    password = "Maximo.2017"

    try:
        common = xmlrpc.client.ServerProxy(f"{odoo_url}/xmlrpc/2/common")
        uid = common.authenticate(db, login, password, {})

        if not uid:
            return {"success": False, "error": "Authentication failed"}

        models = xmlrpc.client.ServerProxy(f"{odoo_url}/xmlrpc/2/object")

        bill_ids = models.execute_kw(
            db,
            uid,
            password,
            "account.move",
            "search",
            [[["move_type", "in", ["in_invoice", "in_refund"]]]],
            {"limit": 1, "order": "id desc"}
        )

        if not bill_ids:
            return {"success": False, "error": "No vendor bills found"}

        bill_id = bill_ids[0]

        message_id = models.execute_kw(
            db,
            uid,
            password,
            "account.move",
            "message_post",
            [[bill_id]],
            {
                "body": (
                    "<strong>⚠️ RN Fiscal Shield SaaS</strong><br/>"
                    "Mensaje de prueba enviado desde la API RN."
                ),
                "message_type": "comment",
                "subtype_xmlid": "mail.mt_note",
            }
        )

        return {
            "success": True,
            "bill_id": bill_id,
            "message_id": message_id,
            "message": "Chatter message posted successfully",
        }

    except Exception as e:
        return {"success": False, "error": str(e)}

@router.get("/api/v1/odoo/vendor-bills-uuid")
def get_vendor_bills_uuid():

    odoo_url = "https://apisat.odoo.com"
    db = "apisat"
    login = "fran@consultorarn.com"
    password = "Maximo.2017"

    try:

        common = xmlrpc.client.ServerProxy(
            f"{odoo_url}/xmlrpc/2/common"
        )

        uid = common.authenticate(
            db,
            login,
            password,
            {}
        )

        if not uid:
            return {
                "success": False,
                "error": "Authentication failed"
            }

        models = xmlrpc.client.ServerProxy(
            f"{odoo_url}/xmlrpc/2/object"
        )

        bills = models.execute_kw(
            db,
            uid,
            password,
            "account.move",
            "search_read",
            [[
                ["move_type", "in", ["in_invoice", "in_refund"]]
            ]],
            {
                "fields": [
                    "id",
                    "name",
                    "ref",
                    "invoice_date",
                    "amount_total",
                    "state",
                    "partner_id"
                ],
                "limit": 20,
                "order": "id desc"
            }
        )

        result = []

        for bill in bills:

            partner_name = None
            partner_vat = None

            partner_id = bill.get("partner_id")

            if partner_id:

                partner = models.execute_kw(
                    db,
                    uid,
                    password,
                    "res.partner",
                    "read",
                    [[partner_id[0]]],
                    {
                        "fields": [
                            "name",
                            "vat"
                        ]
                    }
                )

                if partner:
                    partner_name = partner[0].get("name")
                    partner_vat = partner[0].get("vat")

            result.append({
                "id": bill.get("id"),
                "name": bill.get("name"),
                "ref": bill.get("ref"),
                "invoice_date": bill.get("invoice_date"),
                "amount_total": bill.get("amount_total"),
                "state": bill.get("state"),
                "partner_name": partner_name,
                "partner_vat": partner_vat,
            })

        return {
            "success": True,
            "count": len(result),
            "bills": result
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }
    
@router.get("/api/v1/odoo/check-vendor-risk")
def check_vendor_risk(db_session: Session = Depends(get_db)):
    odoo_url = "https://apisat.odoo.com"
    db = "apisat"
    login = "fran@consultorarn.com"
    password = "Maximo.2017"

    try:
        common = xmlrpc.client.ServerProxy(f"{odoo_url}/xmlrpc/2/common")
        uid = common.authenticate(db, login, password, {})

        if not uid:
            return {
                "success": False,
                "error": "Authentication failed"
            }

        models = xmlrpc.client.ServerProxy(f"{odoo_url}/xmlrpc/2/object")

        bills = models.execute_kw(
            db,
            uid,
            password,
            "account.move",
            "search_read",
            [[
                ["move_type", "in", ["in_invoice", "in_refund"]],
                ["state", "!=", "cancel"]
            ]],
            {
                "fields": [
                    "id",
                    "name",
                    "ref",
                    "partner_id",
                    "amount_total",
                    "state"
                ],
                "limit": 50,
                "order": "id desc"
            }
        )

        checked = 0
        alerted = 0
        results = []

        for bill in bills:
            partner_id = bill.get("partner_id")

            if not partner_id:
                continue

            partner = models.execute_kw(
                db,
                uid,
                password,
                "res.partner",
                "read",
                [[partner_id[0]]],
                {"fields": ["name", "vat"]}
            )

            if not partner:
                continue

            partner_name = partner[0].get("name")
            partner_vat = normalize_rfc(partner[0].get("vat"))

            if not is_valid_rfc(partner_vat):
                continue

            checked += 1

            risk = db_session.query(FiscalRisk).filter(
                FiscalRisk.rfc == partner_vat
            ).first()

            if not risk:
                results.append({
                    "bill_id": bill.get("id"),
                    "partner": partner_name,
                    "rfc": partner_vat,
                    "risk_found": False
                })
                continue

            body = (
                "<strong>⚠️ RN Fiscal Shield SaaS</strong><br/>"
                f"RFC: {risk.rfc}<br/>"
                f"Proveedor: {risk.name or partner_name}<br/>"
                f"Riesgo: {risk.risk_level}<br/>"
                f"Lista: {risk.list_type}<br/>"
                f"Situación: {risk.situation}<br/>"
                f"Mensaje: {risk.message}"
            )

            message_id = models.execute_kw(
                db,
                uid,
                password,
                "account.move",
                "message_post",
                [[bill.get("id")]],
                {
                    "body": body,
                    "message_type": "comment",
                    "subtype_xmlid": "mail.mt_note",
                }
            )

            alerted += 1

            results.append({
                "bill_id": bill.get("id"),
                "partner": partner_name,
                "rfc": partner_vat,
                "risk_found": True,
                "message_id": message_id,
                "risk_level": risk.risk_level,
                "list_type": risk.list_type
            })

        return {
            "success": True,
            "checked": checked,
            "alerted": alerted,
            "results": results
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
