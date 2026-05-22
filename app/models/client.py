from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func

from app.database import Base


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)

    company_rfc = Column(String, nullable=False, unique=True)
    sat_ciec = Column(String, nullable=False)

    odoo_url = Column(String, nullable=False)
    odoo_login = Column(String, nullable=False)
    odoo_password = Column(String, nullable=False)

    alert_email = Column(String)

    onboarding_status = Column(String, default="pending")

    sync_enabled = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())