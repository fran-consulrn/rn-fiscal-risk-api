from fastapi import FastAPI

app = FastAPI(
    title="RN Fiscal Risk API",
    version="1.0.0"
)


@app.get("/")
def root():
    return {
        "message": "RN Fiscal Risk API running"
    }


@app.get("/health")
def health():
    return {
        "status": "ok"
    }


@app.get("/api/v1/risk/{rfc}")
def get_risk(rfc: str):

    demo_blacklist = {
        "XAXX010101000": {
            "found": True,
            "risk_level": "red",
            "list_type": "69-B Definitivo",
            "message": "RFC encontrado en lista SAT."
        }
    }

    result = demo_blacklist.get(rfc.upper())

    if result:
        return result

    return {
        "found": False
    }