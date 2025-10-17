from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from .db import engine, init_db

app = FastAPI()

@app.on_event("startup")
def startup():
    init_db()
    # connectivity check
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.get("/healthz/db")
def db_health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"db_ok": True}
    except Exception as e:
        return JSONResponse({"db_ok": False, "error": str(e)}, status_code=500)
