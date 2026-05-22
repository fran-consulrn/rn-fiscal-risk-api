@router.get("/api/v1/sat/import-first-local-xml-to-odoo")
def import_first_local_xml_to_odoo():
    def _import_single_xml_to_odoo(models, uid, selected_xml):
        with open(selected_xml, "rb") as f:
            selected_data = f.read()

        try:
            parsed = _parse_xml(selected_data)
        except Exception as e:
            return {
                "status": "skipped_invalid_xml",
                "xml_file": selected_xml,
                "error": str(e),
            }

        if parsed["total"] <= 0:
            return {
                "status": "skipped_zero_total",
                "xml_file": selected_xml,
            }

        emisor = parsed["emisor"]

        if emisor is None:
            return {
                "status": "skipped_invalid_xml",
                "xml_file": selected_xml,
                "error": "No emisor found",
            }

        supplier_rfc = emisor.attrib.get("Rfc")
        supplier_name = emisor.attrib.get("Nombre")
        invoice_ref = _build_invoice_ref(parsed)

        existing_move_id = _invoice_exists(
            models,
            uid,
            invoice_ref,
        )

        if existing_move_id:
            return {
                "status": "skipped_existing",
                "xml_file": selected_xml,
                "move_id": existing_move_id,
                "ref": invoice_ref,
                "uuid": parsed["uuid"],
            }

        partner_id = _get_or_create_partner(
            models,
            uid,
            supplier_rfc,
            supplier_name,
        )

        invoice_lines = _build_invoice_lines(
            parsed["conceptos"]
        )

        move_id = models.execute_kw(
            ODOO_DB,
            uid,
            ODOO_PASSWORD,
            "account.move",
            "create",
            [{
                "move_type": "in_invoice",
                "company_id": ODOO_COMPANY_ID,
                "partner_id": partner_id,
                "invoice_date": (
                    parsed["fecha"][:10]
                    if parsed["fecha"]
                    else False
                ),
                "ref": invoice_ref,
                "invoice_origin": parsed["uuid"],
                "invoice_line_ids": invoice_lines,
            }],
            {
                "context": ODOO_CONTEXT,
            },
        )

        xml_filename = os.path.basename(selected_xml)

        attachment_id = models.execute_kw(
            ODOO_DB,
            uid,
            ODOO_PASSWORD,
            "ir.attachment",
            "create",
            [{
                "name": xml_filename,
                "datas": base64.b64encode(
                    selected_data
                ).decode("utf-8"),
                "res_model": "account.move",
                "res_id": move_id,
                "mimetype": "application/xml",
            }],
            {
                "context": ODOO_CONTEXT,
            },
        )

        models.execute_kw(
            ODOO_DB,
            uid,
            ODOO_PASSWORD,
            "account.move",
            "message_post",
            [[move_id]],
            {
                "body": (
                    "<strong>RN Fiscal Shield SaaS</strong><br/>"
                    "Factura creada automáticamente desde XML SAT.<br/>"
                    f"UUID: {parsed['uuid']}<br/>"
                    f"XML: {xml_filename}"
                ),
                "message_type": "comment",
                "subtype_xmlid": "mail.mt_note",
                "attachment_ids": [attachment_id],
                "context": ODOO_CONTEXT,
            },
        )

        return {
            "status": "imported",
            "xml_file": selected_xml,
            "move_id": move_id,
            "attachment_id": attachment_id,
            "uuid": parsed["uuid"],
            "ref": invoice_ref,
            "supplier": supplier_name,
            "supplier_rfc": supplier_rfc,
        }


    try:
        uid, models = _get_odoo_models()

        if not uid:
            return {
                "success": False,
                "error": "Authentication failed",
            }

        scanned = 0
        skipped_existing = 0
        skipped_zero_total = 0
        skipped_invalid_xml = 0

        for root_dir, dirs, files in os.walk(XML_FOLDER):
            for file in files:
                if not file.lower().endswith(".xml"):
                    continue

                selected_xml = os.path.join(root_dir, file)
                scanned += 1

                result = _import_single_xml_to_odoo(
                    models,
                    uid,
                    selected_xml,
                )

                status = result.get("status")

                if status == "imported":
                    result.update({
                        "success": True,
                        "scanned": scanned,
                        "skipped_existing": skipped_existing,
                        "skipped_zero_total": skipped_zero_total,
                        "skipped_invalid_xml": skipped_invalid_xml,
                    })
                    return result

                if status == "skipped_existing":
                    skipped_existing += 1
                    continue

                if status == "skipped_zero_total":
                    skipped_zero_total += 1
                    continue

                if status == "skipped_invalid_xml":
                    skipped_invalid_xml += 1
                    continue

        return {
            "success": False,
            "error": "No new XML invoices found to import",
            "scanned": scanned,
            "skipped_existing": skipped_existing,
            "skipped_zero_total": skipped_zero_total,
            "skipped_invalid_xml": skipped_invalid_xml,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


@router.get("/api/v1/sat/auto-sync-local-xmls")
def auto_sync_local_xmls(limit: int = 25):
    try:
        uid, models = _get_odoo_models()

        if not uid:
            return {
                "success": False,
                "error": "Authentication failed",
            }

        scanned = 0
        imported = 0
        skipped_existing = 0
        skipped_zero_total = 0
        skipped_invalid_xml = 0
        errors = 0
        results = []

        for root_dir, dirs, files in os.walk(XML_FOLDER):
            for file in files:
                if not file.lower().endswith(".xml"):
                    continue

                if imported >= limit:
                    return {
                        "success": True,
                        "message": "Auto sync limit reached",
                        "limit": limit,
                        "scanned": scanned,
                        "imported": imported,
                        "skipped_existing": skipped_existing,
                        "skipped_zero_total": skipped_zero_total,
                        "skipped_invalid_xml": skipped_invalid_xml,
                        "errors": errors,
                        "results": results,
                    }

                selected_xml = os.path.join(root_dir, file)
                scanned += 1

                try:
                    result = _import_single_xml_to_odoo(
                        models,
                        uid,
                        selected_xml,
                    )
                except Exception as e:
                    errors += 1
                    result = {
                        "status": "error",
                        "xml_file": selected_xml,
                        "error": str(e),
                    }

                status = result.get("status")

                if status == "imported":
                    imported += 1
                elif status == "skipped_existing":
                    skipped_existing += 1
                elif status == "skipped_zero_total":
                    skipped_zero_total += 1
                elif status == "skipped_invalid_xml":
                    skipped_invalid_xml += 1
                elif status == "error":
                    errors += 1
                else:
                    errors += 1

                results.append(result)

        return {
            "success": True,
            "message": "Auto sync completed",
            "limit": limit,
            "scanned": scanned,
            "imported": imported,
            "skipped_existing": skipped_existing,
            "skipped_zero_total": skipped_zero_total,
            "skipped_invalid_xml": skipped_invalid_xml,
            "errors": errors,
            "results": results,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }