from app.database import engine
from app.models.client import Client

Client.metadata.create_all(bind=engine)

app.include_router(onboarding_router)