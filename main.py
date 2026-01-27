import os, sqlite3
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException

app = FastAPI(title="Musik Android API")

DB_DIR = "/data"
DB_PATH = f"{DB_DIR}/musik.db"


def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
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
        "endpoints": {
            "callback": [
                "POST /callback",
                "POST /callback/suno"
            ],
            "list": "GET /audios",
            "detail": "GET /audio/{audio_id}"
        }
    }


# =========================
# CALLBACK HANDLER (UMUM)
# =========================
async def handle_callback(request: Request):
    try:
        payload = await request.json()
    except:
        return {"ok": True}

    data = payload.get("data") or {}
    items = data.get("data") or []

    if not items:
        return {"ok": True}

    c = db()
    for i in items:
        c.execute("""
        INSERT INTO audios (
            audio_id, title, tags, duration,
            audio_url, stream_audio_url, image_url, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(audio_id) DO UPDATE SET
            title=excluded.title,
            tags=excluded.tags,
            duration=excluded.duration,
            audio_url=excluded.audio_url,
            stream_audio_url=excluded.stream_audio_url,
            image_url=excluded.image_url,
            created_at=excluded.created_at
        """, (
            i.get("id"),
            i.get("title"),
            i.get("tags"),
            i.get("duration"),
            i.get("audio_url"),
            i.get("stream_audio_url"),
            i.get("image_url"),
            datetime.utcnow().isoformat()
        ))
    c.commit()
    c.close()
    return {"success": True}


# ✅ CALLBACK STANDARD
@app.post("/callback")
async def callback(request: Request):
    return await handle_callback(request)


# ✅ CALLBACK SUNO (INI YANG KURANG)
@app.post("/callback/suno")
async def callback_suno(request: Request):
    return await handle_callback(request)


# =========================
# API ANDROID
# =========================
@app.get("/audios")
def audios():
    c = db()
    rows = c.execute("SELECT * FROM audios ORDER BY id DESC").fetchall()
    c.close()
    return {"count": len(rows), "data": [dict(r) for r in rows]}


@app.get("/audio/{audio_id}")
def audio_detail(audio_id: str):
    c = db()
    r = c.execute("SELECT * FROM audios WHERE audio_id=?", (audio_id,)).fetchone()
    c.close()
    if not r:
        raise HTTPException(404, "Not found")
    return dict(r)


