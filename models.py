from datetime import datetime

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date

from database import Base


class FiscalRisk(Base):
    __tablename__ = "fiscal_risks"

    id = Column(Integer, primary_key=True, index=True)

    rfc = Column(String, unique=True, index=True, nullable=False)
    name = Column(String)
    risk_level = Column(String)
    list_type = Column(String)
    situation = Column(String)
    source = Column(String)
    publication_date = Column(Date, nullable=True)
    message = Column(String)


class RNFiscalClient(Base):
    __tablename__ = "rn_fiscal_clients"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String, unique=True, index=True, nullable=False)

    company_name = Column(String, nullable=True)
    company_rfc = Column(String, index=True, nullable=False)

    odoo_url = Column(String, nullable=False)
    odoo_database = Column(String, nullable=True)
    odoo_login = Column(String, nullable=False)
    odoo_password = Column(String, nullable=False)

    odoo_company_id = Column(Integer, nullable=True)
    odoo_company_name = Column(String, nullable=True)

    sat_ciec = Column(String, nullable=False)
    alert_email = Column(String, nullable=True)

    auto_validate_risk = Column(Boolean, default=False)
    sync_enabled = Column(Boolean, default=True)

    onboarding_status = Column(String, default="pending")
    onboarding_message = Column(String, nullable=True)

    source = Column(String, default="odoo_module")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class RNFiscalXMLDocument(Base):
    __tablename__ = "rn_fiscal_xml_documents"

    id = Column(Integer, primary_key=True, index=True)

    customer_id = Column(String, index=True, nullable=False)
    uuid = Column(String, index=True, nullable=False)

    filename = Column(String, nullable=True)

    supplier_rfc = Column(String, index=True, nullable=True)
    supplier_name = Column(String, nullable=True)

    receiver_rfc = Column(String, index=True, nullable=True)
    receiver_name = Column(String, nullable=True)

    folio = Column(String, nullable=True)
    serie = Column(String, nullable=True)
    fecha = Column(String, nullable=True)

    subtotal = Column(String, nullable=True)
    total = Column(String, nullable=True)
    currency = Column(String, nullable=True)

    status = Column(String, default="received")
    message = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)