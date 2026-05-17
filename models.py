from sqlalchemy import Column, Integer, String, Date

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