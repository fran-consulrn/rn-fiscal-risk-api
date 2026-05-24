from fastapi import FastAPI, Depends, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import Base, engine, SessionLocal
from models import FiscalRisk, RNFiscalClient, RNFiscalXMLDocument
from odoo_saas import router as odoo_saas_router

import csv
import io
import xmlrpc.client
import json
import base64
from datetime import datetime

Base.metadata.create_all(bind=engine)

with engine.begin() as conn:
    conn.execute(text(
        "ALTER TABLE rn_fiscal_xml_documents "
        "DROP CONSTRAINT IF EXISTS rn_fiscal_xml_documents_uuid_key"
    ))
    conn.execute(text(
        "DROP INDEX IF EXISTS ix_rn_fiscal_xml_documents_uuid"
    ))
    conn.execute(text(
        "ALTER TABLE rn_fiscal_xml_documents "
        "ADD COLUMN IF NOT EXISTS concepts_json TEXT"
    ))
    conn.execute(text(
        "ALTER TABLE rn_fiscal_xml_documents "
        "ADD COLUMN IF NOT EXISTS xml_content_base64 TEXT"
    ))
    conn.execute(text("ALTER TABLE rn_fiscal_xml_documents ADD COLUMN IF NOT EXISTS uuid_sat VARCHAR"))
    conn.execute(text("ALTER TABLE rn_fiscal_xml_documents ADD COLUMN IF NOT EXISTS payment_method VARCHAR"))
    conn.execute(text("ALTER TABLE rn_fiscal_xml_documents ADD COLUMN IF NOT EXISTS payment_form VARCHAR"))
    conn.execute(text("ALTER TABLE rn_fiscal_xml_documents ADD COLUMN IF NOT EXISTS document_type VARCHAR"))
    conn.execute(text("ALTER TABLE rn_fiscal_xml_documents ADD COLUMN IF NOT EXISTS exchange_rate VARCHAR"))
    conn.execute(text("ALTER TABLE rn_fiscal_xml_documents ADD COLUMN IF NOT EXISTS place_of_issue VARCHAR"))
    conn.execute(text("ALTER TABLE rn_fiscal_xml_documents ADD COLUMN IF NOT EXISTS cfdi_usage VARCHAR"))
    conn.execute(text("ALTER TABLE rn_fiscal_xml_documents ADD COLUMN IF NOT EXISTS issuer_tax_regime VARCHAR"))
    conn.execute(text("ALTER TABLE rn_fiscal_xml_documents ADD COLUMN IF NOT EXISTS receiver_tax_regime VARCHAR"))
    conn.execute(text("ALTER TABLE rn_fiscal_xml_documents ADD COLUMN IF NOT EXISTS discount VARCHAR"))
    conn.execute(text("ALTER TABLE rn_fiscal_xml_documents ADD COLUMN IF NOT EXISTS tax_transferred_total VARCHAR"))
    conn.execute(text("ALTER TABLE rn_fiscal_xml_documents ADD COLUMN IF NOT EXISTS tax_withheld_total VARCHAR"))

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
    db: Session = Depends(get_db),
):
    import xml.etree.ElementTree as ET

    content = await file.read()

    xml_content_base64 = base64.b64encode(content).decode("utf-8")

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

    conceptos = root.findall(".//cfdi:Concepto", namespaces)
    concepts = []

    for concepto in conceptos:
        concept_taxes = []

        traslados = concepto.findall(".//cfdi:Traslado", namespaces)
        for traslado in traslados:
            concept_taxes.append({
                "tax_type": "traslado",
                "base": traslado.attrib.get("Base"),
                "impuesto": traslado.attrib.get("Impuesto"),
                "tipo_factor": traslado.attrib.get("TipoFactor"),
                "tasa_cuota": traslado.attrib.get("TasaOCuota"),
                "importe": traslado.attrib.get("Importe"),
            })

        retenciones = concepto.findall(".//cfdi:Retencion", namespaces)
        for retencion in retenciones:
            concept_taxes.append({
                "tax_type": "retencion",
                "base": retencion.attrib.get("Base"),
                "impuesto": retencion.attrib.get("Impuesto"),
                "tipo_factor": retencion.attrib.get("TipoFactor"),
                "tasa_cuota": retencion.attrib.get("TasaOCuota"),
                "importe": retencion.attrib.get("Importe"),
            })

        concepts.append({
            "clave_prod_serv": concepto.attrib.get("ClaveProdServ"),
            "cantidad": concepto.attrib.get("Cantidad"),
            "clave_unidad": concepto.attrib.get("ClaveUnidad"),
            "unidad": concepto.attrib.get("Unidad"),
            "descripcion": concepto.attrib.get("Descripcion"),
            "valor_unitario": concepto.attrib.get("ValorUnitario"),
            "importe": concepto.attrib.get("Importe"),
            "objeto_imp": concepto.attrib.get("ObjetoImp"),
            "taxes": concept_taxes,
        })

    concepts_json = json.dumps(concepts, ensure_ascii=False)

    if not uuid:
        return {
            "success": False,
            "customer_id": customer_id,
            "filename": file.filename,
            "error": "XML does not contain UUID.",
        }

    clean_uuid = uuid.lower()

    existing = (
        db.query(RNFiscalXMLDocument)
        .filter(
            RNFiscalXMLDocument.uuid == clean_uuid,
            RNFiscalXMLDocument.customer_id == customer_id,
        )
        .first()
    )

    if existing:
        return {
            "success": True,
            "duplicate": True,
            "status": "duplicate",
            "customer_id": existing.customer_id,
            "filename": existing.filename,
            "uuid": existing.uuid,
            "supplier_rfc": existing.supplier_rfc,
            "supplier_name": existing.supplier_name,
            "receiver_rfc": existing.receiver_rfc,
            "receiver_name": existing.receiver_name,
            "folio": existing.folio,
            "serie": existing.serie,
            "fecha": existing.fecha,
            "subtotal": existing.subtotal,
            "total": existing.total,
            "currency": existing.currency,
            "message": "XML already exists. Duplicate skipped.",
        }

    supplier_rfc = emisor.attrib.get("Rfc") if emisor is not None else None
    supplier_name = emisor.attrib.get("Nombre") if emisor is not None else None
    receiver_rfc = receptor.attrib.get("Rfc") if receptor is not None else None
    receiver_name = receptor.attrib.get("Nombre") if receptor is not None else None
    folio = comprobante.attrib.get("Folio")
    serie = comprobante.attrib.get("Serie")
    fecha = comprobante.attrib.get("Fecha")
    subtotal = comprobante.attrib.get("SubTotal")
    total = comprobante.attrib.get("Total")
    currency = comprobante.attrib.get("Moneda")

    xml_document = RNFiscalXMLDocument(
        customer_id=customer_id,
        uuid=clean_uuid,
        filename=file.filename,
        supplier_rfc=supplier_rfc,
        supplier_name=supplier_name,
        receiver_rfc=receiver_rfc,
        receiver_name=receiver_name,
        folio=folio,
        serie=serie,
        fecha=fecha,
        subtotal=subtotal,
        total=total,
        currency=currency,
        concepts_json=concepts_json,
        xml_content_base64=xml_content_base64,
        status="received",
        message="XML received and parsed successfully.",
    )

    db.add(xml_document)
    db.commit()
    db.refresh(xml_document)

    return {
        "success": True,
        "duplicate": False,
        "status": xml_document.status,
        "customer_id": xml_document.customer_id,
        "filename": xml_document.filename,
        "uuid": xml_document.uuid,
        "supplier_rfc": xml_document.supplier_rfc,
        "supplier_name": xml_document.supplier_name,
        "receiver_rfc": xml_document.receiver_rfc,
        "receiver_name": xml_document.receiver_name,
        "folio": xml_document.folio,
        "serie": xml_document.serie,
        "fecha": xml_document.fecha,
        "subtotal": xml_document.subtotal,
        "total": xml_document.total,
        "currency": xml_document.currency,
        "concepts_count": len(concepts),
        "concepts": concepts,
        "message": xml_document.message,
    }

app.include_router(odoo_saas_router)

@app.get("/api/v1/xml/documents/{customer_id}")
def get_xml_documents(
    customer_id: str,
    db: Session = Depends(get_db),
):
    documents = (
        db.query(RNFiscalXMLDocument)
        .filter(RNFiscalXMLDocument.customer_id == customer_id)
        .order_by(RNFiscalXMLDocument.created_at.desc())
        .all()
    )

    return {
        "success": True,
        "customer_id": customer_id,
        "count": len(documents),
        "documents": [
            {
                "id": doc.id,
                "uuid": doc.uuid,
                "filename": doc.filename,
                "supplier_rfc": doc.supplier_rfc,
                "supplier_name": doc.supplier_name,
                "receiver_rfc": doc.receiver_rfc,
                "receiver_name": doc.receiver_name,
                "folio": doc.folio,
                "serie": doc.serie,
                "fecha": doc.fecha,
                "subtotal": doc.subtotal,
                "total": doc.total,
                "currency": doc.currency,
                "concepts_count": len(json.loads(doc.concepts_json or "[]")),
                "status": doc.status,
                "message": doc.message,
                "created_at": doc.created_at,
            }
            for doc in documents
        ],
    }

@app.post("/api/v1/xml/send-to-odoo/{xml_id}")
def send_xml_to_odoo(
    xml_id: int,
    db: Session = Depends(get_db),
):
    xml_document = (
        db.query(RNFiscalXMLDocument)
        .filter(RNFiscalXMLDocument.id == xml_id)
        .first()
    )

    if not xml_document:
        return {
            "success": False,
            "error": "XML document not found.",
        }

    client = (
        db.query(RNFiscalClient)
        .filter(RNFiscalClient.customer_id == xml_document.customer_id)
        .first()
    )

    if not client:
        return {
            "success": False,
            "error": "Client not found.",
        }

    try:
        common = xmlrpc.client.ServerProxy(
            f"{client.odoo_url}/xmlrpc/2/common",
            allow_none=True,
        )

        uid = common.authenticate(
            client.odoo_database,
            client.odoo_login,
            client.odoo_password,
            {},
        )

        if not uid:
            return {
                "success": False,
                "error": "Odoo authentication failed.",
            }

        models = xmlrpc.client.ServerProxy(
            f"{client.odoo_url}/xmlrpc/2/object",
            allow_none=True,
        )

        bills = models.execute_kw(
            client.odoo_database,
            uid,
            client.odoo_password,
            "account.move",
            "search_read",
            [[
                ["move_type", "in", ["in_invoice", "in_refund"]],
                ["state", "!=", "cancel"],
            ]],
            {
                "fields": ["id", "name", "ref"],
                "limit": 100,
                "order": "id desc",
            },
        )

        matched_bill = None

        for bill in bills:
            ref = (bill.get("ref") or "").lower()

            if xml_document.uuid in ref:
                matched_bill = bill
                break

        if not matched_bill:
            partner_domain = [["vat", "=", xml_document.supplier_rfc]]

            partner_ids = models.execute_kw(
                client.odoo_database,
                uid,
                client.odoo_password,
                "res.partner",
                "search",
                [partner_domain],
                {"limit": 1},
            )

            if partner_ids:
                partner_id = partner_ids[0]
            else:
                partner_id = models.execute_kw(
                    client.odoo_database,
                    uid,
                    client.odoo_password,
                    "res.partner",
                    "create",
                    [{
                        "name": xml_document.supplier_name or xml_document.supplier_rfc or "Proveedor CFDI",
                        "vat": xml_document.supplier_rfc or False,
                        "company_type": "company",
                    }],
                )

            account_ids = models.execute_kw(
                client.odoo_database,
                uid,
                client.odoo_password,
                "account.account",
                "search",
                [[
                    ["account_type", "=", "expense"],
                ]],
                {"limit": 1},
            )
                
            if not account_ids:
                return {
                    "success": False,
                    "error": "No expense account found in Odoo.",
                }

            bill_ref = f"{xml_document.serie or ''}-{xml_document.folio or ''}-{xml_document.uuid}"

            concepts = json.loads(xml_document.concepts_json or "[]")
            invoice_lines = []

            def find_purchase_tax_ids(concept):
                tax_ids = []

                for tax in concept.get("taxes") or []:
                    if tax.get("tax_type") != "traslado":
                        continue

                    if tax.get("impuesto") != "002":
                        continue

                    if tax.get("tipo_factor") != "Tasa":
                        continue

                    tasa_cuota = tax.get("tasa_cuota")
                    if not tasa_cuota:
                        continue

                    try:
                        tax_amount = round(float(tasa_cuota) * 100, 6)
                    except Exception:
                        continue

                    found_tax_ids = models.execute_kw(
                        client.odoo_database,
                        uid,
                        client.odoo_password,
                        "account.tax",
                        "search",
                        [[
                            ["type_tax_use", "=", "purchase"],
                            ["amount_type", "=", "percent"],
                            ["amount", "=", tax_amount],
                            ["active", "=", True],
                        ]],
                        {"limit": 1},
                    )

                    if found_tax_ids:
                        tax_ids.append(found_tax_ids[0])

                return tax_ids

            for concept in concepts:
                tax_ids = find_purchase_tax_ids(concept)

                line_vals = {
                    "name": concept.get("descripcion") or f"CFDI {xml_document.uuid}",
                    "quantity": float(concept.get("cantidad") or 1.0),
                    "price_unit": float(concept.get("valor_unitario") or concept.get("importe") or 0.0),
                    "account_id": account_ids[0],
                }

                if tax_ids:
                    line_vals["tax_ids"] = [(6, 0, tax_ids)]

                invoice_lines.append((0, 0, line_vals))

            if not invoice_lines:
                invoice_lines.append((0, 0, {
                    "name": f"CFDI {xml_document.uuid}",
                    "quantity": 1.0,
                    "price_unit": float(xml_document.subtotal or xml_document.total or 0.0),
                    "account_id": account_ids[0],
                }))

            move_vals = {
                "move_type": "in_invoice",
                "partner_id": partner_id,
                "ref": bill_ref,
                "invoice_date": (xml_document.fecha or "")[:10] or False,
                "invoice_line_ids": invoice_lines,
            }
            if client.odoo_company_id:
                move_vals["company_id"] = client.odoo_company_id

            created_bill_id = models.execute_kw(
                client.odoo_database,
                uid,
                client.odoo_password,
                "account.move",
                "create",
                [move_vals],
            )

            matched_bill = {
                "id": created_bill_id,
                "name": "Draft Vendor Bill",
                "ref": bill_ref,
            }

        attachment_id = None

        if xml_document.xml_content_base64:
            attachment_id = models.execute_kw(
                client.odoo_database,
                uid,
                client.odoo_password,
                "ir.attachment",
                "create",
                [{
                    "name": xml_document.filename or f"{xml_document.uuid}.xml",
                    "type": "binary",
                    "datas": xml_document.xml_content_base64,
                    "res_model": "account.move",
                    "res_id": matched_bill["id"],
                    "mimetype": "application/xml",
                }],
            )            

        body = (
            "<strong>✅ RN Fiscal Shield SaaS</strong><br/>"
            f"XML UUID detectado: {xml_document.uuid}<br/>"
            f"Proveedor: {xml_document.supplier_name}<br/>"
            f"RFC: {xml_document.supplier_rfc}<br/>"
            f"Total: {xml_document.total} {xml_document.currency}"
        )

        message_kwargs = {
            "body": body,
            "message_type": "comment",
            "subtype_xmlid": "mail.mt_note",
        }

        if attachment_id:
            message_kwargs["attachment_ids"] = [attachment_id]

        message_id = models.execute_kw(
            client.odoo_database,
            uid,
            client.odoo_password,
            "account.move",
            "message_post",
            [[matched_bill["id"]]],
            message_kwargs,
        )
        
        xml_document.status = "synced"
        xml_document.message = "XML synced to Odoo successfully."

        db.commit()

        return {
            "success": True,
            "xml_id": xml_document.id,
            "bill_id": matched_bill["id"],
            "message_id": message_id,
            "status": xml_document.status,
            "message": xml_document.message,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }