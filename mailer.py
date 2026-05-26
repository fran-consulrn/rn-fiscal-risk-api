import os
import requests

RESEND_API_KEY = os.getenv("RESEND_API_KEY")

ONBOARDING_TO_EMAIL = os.getenv(
    "ONBOARDING_TO_EMAIL",
    "hola@consultorarn.com",
)

FROM_EMAIL = os.getenv(
    "FROM_EMAIL",
    "onboarding@resend.dev",
)


def send_new_onboarding_email(client):

    if not RESEND_API_KEY:
        print("Missing RESEND_API_KEY")
        return False

    subject = (
        f"🚀 Nuevo onboarding RN Fiscal Shield - "
        f"{client.company_rfc}"
    )

    html = f"""
    <h2>Nuevo cliente pendiente de activación</h2>

    <p>
        <strong>Cliente:</strong>
        {client.company_name or "Sin nombre"}
    </p>

    <p>
        <strong>RFC:</strong>
        {client.company_rfc}
    </p>

    <p>
        <strong>Customer ID:</strong>
        {client.customer_id}
    </p>

    <hr>

    <p>
        <strong>Odoo URL:</strong>
        {client.odoo_url}
    </p>

    <p>
        <strong>Database:</strong>
        {client.odoo_database}
    </p>

    <p>
        <strong>Usuario:</strong>
        {client.odoo_login}
    </p>

    <hr>

    <h3>Acción requerida:</h3>

    <ul>
        <li>Crear/configurar cuenta OneFacture</li>
        <li>Ligar carpeta del RFC</li>
        <li>Activar cliente desde API</li>
        <li>Validar conexión Odoo</li>
    </ul>
    """

    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "from": FROM_EMAIL,
            "to": [ONBOARDING_TO_EMAIL],
            "subject": subject,
            "html": html,
        },
        timeout=15,
    )

    print(response.status_code)
    print(response.text)

    return response.status_code in (200, 201)