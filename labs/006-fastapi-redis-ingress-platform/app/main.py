from fastapi import FastAPI

app = FastAPI(title="Mission 006 - Payment API")


@app.get("/")
async def root():
    return {"service": "payment-api", "status": "running"}


@app.get("/health/live")
async def liveness():
    return {"status": "alive"}


@app.get("/health/ready")
async def readiness():
    return {"status": "ready"}
