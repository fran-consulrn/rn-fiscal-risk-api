import os
import smtplib

from email.mime.text import MIMEText


SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
ONBOARDING_TO_EMAIL = os.environ.get(
    "ONBOARDING_TO_EMAIL",
    "hola@consultorarn.com",
)


def send_new_onboarding_email(client):
    if not SMTP_USER or not SMTP_PASSWORD:
        return False

    subject = "Nuevo onboarding RN Fiscal Shield"

    body = f"""
Nuevo cliente pendiente de activación.

Cliente: {client.company_name or "Sin nombre"}
RFC: {client.company_rfc}
Customer ID: {client.customer_id}

Odoo URL:
{client.odoo_url}

Base de datos:
{client.odoo_database}

Estatus:
{client.onboarding_status}

Acción requerida:
1. Crear/configurar cuenta en OneFacture.
2. Ligar carpeta del RFC.
3. Activar cliente desde /api/v1/admin/activate-client.
"""

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = ONBOARDING_TO_EMAIL

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(
            SMTP_USER,
            [ONBOARDING_TO_EMAIL],
            msg.as_string(),
        )

    return True