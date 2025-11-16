
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn
from typing import Optional, Dict, Any, Set

app = FastAPI()

LATEST_STATUS: Optional[Dict[str, Any]] = None
KNOWN_COMPONENTS: Set[str] = set()


@app.get("/health")
async def health():
    return {"status": "ok", "message": "webhook worker running"}


@app.get("/status")
async def get_status():
    if LATEST_STATUS is None:
        return JSONResponse(
            {
                "available": False,
                "message": "No heartbeat received yet from watcher.",
            },
            status_code=200,
        )

    return JSONResponse(
        {
            "available": True,
            "latest_status": LATEST_STATUS,
            "known_components": sorted(list(KNOWN_COMPONENTS)),
        },
        status_code=200,
    )


@app.post("/webhook")
async def handle_webhook(request: Request):
    global LATEST_STATUS, KNOWN_COMPONENTS

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    event = body.get("event", "unknown")
    provider = body.get("provider", "unknown")

    print("\n Webhook received")
    print(f"Event:    {event}")
    print(f"Provider: {provider}")
    print(f"Payload:  {body}\n")

    # 1️⃣ Heartbeat: store latest overall status
    if event == "status.heartbeat":
        LATEST_STATUS = body
        impacted = body.get("impacted_components", [])
        for c in impacted:
            KNOWN_COMPONENTS.add(c)
        print(" Stored latest heartbeat.\n")

    # 2️⃣ Incident updates: also learn about components from here
    if event == "incident.update":
        components = body.get("components", [])
        for c in components:
            KNOWN_COMPONENTS.add(c)
        print(f" Updated known components from incident.update: {components}\n")

    # (optional) you could also handle "status.change" similarly

    return JSONResponse({"status": "ok"})


if __name__ == '__main__':
    uvicorn.run(
        "webhook_worker:app",
        host="127.0.0.1",
        port=8000,
        log_level="info",
        reload=False,
    )
