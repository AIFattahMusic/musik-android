import os, sqlite3
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException

app = FastAPI(title="Musik Android API")

# =========================
# STORAGE (ANTI PERMISSION ERROR)
# =========================
if os.path.exists("/data"):
    DB_DIR = "/data"
else:
    DB_DIR = "/tmp"   # fallback aman di Render

DB_PATH = f"{DB_DIR}/musik.db"


def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


@app.on_event("startup")
def startup():
    os.makedirs(DB_DIR, exist_ok=True)
    c = db()
    c.execute("""
    CREATE TABLE IF NOT EXISTS audios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        audio_id TEXT UNIQUE,
        title TEXT,
        tags TEXT,
        duration REAL,
        audio_url TEXT,
        stream_audio_url TEXT,
        image_url TEXT,
        created_at TEXT
    )
    """)
    c.commit()
    c.close()


@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "Musik Android API",
        "db_path": DB_PATH,
        "endpoints": {
            "callback": ["POST /callback", "POST /callback/suno"],
            "list": "GET /audios",
            "detail": "GET /audio/{audio_id}"
        }
    }


# =========================
# CALLBACK HANDLER
# =========================
async def handle_callback(req: Request):
    try:
        payload = await req.json()
    except:
        return {"ok": True}

    items = (payload.get("data") or {}).get("data") or []
    if not items:
        return {"



