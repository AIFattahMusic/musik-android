import sqlite3
import uuid
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException

app = FastAPI(
    title="Musik Android API",
    version="1.0.0"
)

# =========================
# DATABASE (AMAN DI RENDER)
# =========================
DB_PATH = "musik.db"


def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@app.on_event("startup")
def startup():
    conn = get_db()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS audios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id TEXT,
        audio_id TEXT,
        title TEXT,
        prompt TEXT,
        audio_url TEXT,
        created_at TEXT
    )
    """)
    conn.commit()
    conn.close()


# =========================
# ROOT
# =========================
@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "Musik Android API",
        "endpoints": {
            "generate": "POST /generate",
            "callback": [
                "POST /callback",
                "POST /callback/suno"
            ],
            "list": "GET /audios",
            "detail": "GET /audio/{audio_id}"
        }
    }


# =========================
# GENERATE (ANDROID PAKAI)
# =========================
@app.post("/generate")
def generate(payload: dict):
    prompt = payload.get("prompt")
    if not prompt:
        raise HTTPException(400, "prompt is required")

    task_id = str(uuid.uuid4())

    conn = get_db()
    conn.execute("""
        INSERT INTO audios (task_id, prompt, created_at)
        VALUES (?, ?, ?)
    """, (
        task_id,
        prompt,
        datetime.utcnow().isoformat()
    ))
    conn.commit()
    conn.close()

    return {
        "success": True,
        "task_id": task_id,
        "message": "Task created. Waiting for callback."
    }


# =========================
# CALLBACK HANDLER (UMUM)
# =========================
async def handle_callback(req: Request):
    try:
        payload = await req.json()
    except Exception:
        return {"ok": True}

    data = payload.get("data") or {}
    task_id = data.get("task_id")
    items = data.get("data") or []

    if not task_id or not items:
        return {"ok": True}

    conn = get_db()
    for item in items:
        conn.execute("""
        UPDATE audios SET
            audio_id = ?,
            title = ?,
            audio_url = ?,
            created_at = ?
        WHERE task_id = ?
        """, (
            item.get("id"),
            item.get("title"),
            item.get("audio_url"),
            datetime.utcnow().isoformat(),
            task_id
        ))
    conn.commit()
    conn.close()

    return {"success": True}


# =========================
# CALLBACK (GENERIC)
# =========================
@app.post("/callback")
async def callback(req: Request):
    return await handle_callback(req)


# =========================
# CALLBACK SUNO (INI YANG SERING DIPAKAI)
# =========================
@app.post("/callback/suno")
async def callback_suno(req: Request):
    return await handle_callback(req)


# =========================
# LIST AUDIO (ANDROID)
# =========================
@app.get("/audios")
def audios():
    conn = get_db()
    rows = conn.execute("""
        SELECT audio_id, title, audio_url, created_at
        FROM audios
        WHERE audio_id IS NOT NULL
        ORDER BY id DESC
    """).fetchall()
    conn.close()

    return {
        "count": len(rows),
        "data": [dict(r) for r in rows]
    }


# =========================
# DETAIL AUDIO
# =========================
@app.get("/audio/{audio_id}")
def audio_detail(audio_id: str):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM audios WHERE audio_id=?",
        (audio_id,)
    ).fetchone()
    conn.close()

    if not row:
        raise HTTPException(404, "Audio not found")

    return dict(row)

