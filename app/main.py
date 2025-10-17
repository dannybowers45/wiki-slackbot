from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse

app = FastAPI()

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.post("/slack/commands")
async def slack_commands(request: Request):
    # Minimal ack; replace later with real handler + signature check
    return PlainTextResponse("OK")

@app.post("/slack/events")
async def slack_events(request: Request):
    # Handle Slack URL verification during Event Subscriptions
    try:
        body = await request.json()
        if body.get("type") == "url_verification":
            return PlainTextResponse(body.get("challenge", ""))
    except Exception:
        pass
    return JSONResponse({"ok": True})
