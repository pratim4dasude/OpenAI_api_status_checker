from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI()

# ---------------------------
# HEALTH CHECK ENDPOINT
# ---------------------------
@app.get("/health")
@app.get("/")   # optional root health
async def health_check():
    return JSONResponse({"status": "healthy", "service": "webhook-receiver"})


# ---------------------------
# WEBHOOK HANDLER
# ---------------------------
@app.post("/webhook")
async def handle_webhook(request: Request):
    body = await request.json()
    event = body.get("event", "unknown")
    provider = body.get("provider", "unknown")

    print("\n📩 Webhook received")
    print(f"Event:    {event}")
    print(f"Provider: {provider}")
    print(f"Payload:  {body}\n")

    return JSONResponse({"status": "ok"})


# ---------------------------
# UVICORN STARTER
# ---------------------------
if __name__ == '__main__':
    uvicorn.run(
        "webhook_worker:app",
        host="127.0.0.1",
        port=8000,
        log_level="info",
        reload=False  # reload cannot be used when embedding
    )
