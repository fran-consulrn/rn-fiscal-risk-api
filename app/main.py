from fastapi import FastAPI

from app.api.onboarding import router as onboarding_router
from app.database import engine
from app.models.client import Client
from sat_sync import router as sat_sync_router

app = FastAPI(
    title="RN Fiscal Risk API"
)

Client.metadata.create_all(bind=engine)

app.include_router(onboarding_router)
app.include_router(sat_sync_router)


@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "RN Fiscal Risk API",
    }