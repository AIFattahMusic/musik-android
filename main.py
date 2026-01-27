import sqlite3
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException

app = FastAPI(title="Musik Android API")

# =========================
# DATABASE (AMAN DI RENDER)
# =========================
DB_PATH = "musik.db"  # JANGAN pakai /data


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
    conn.commit()
    conn.close()


# =========================
# ROOT (CEK API HIDUP)
# =========================
@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "Musik Android API",
        "endpoints": {
            "callback": "POST /callback/suno",
            "list": "GET /audios",
            "detail": "GET /audio/{audio_id}"
        }
    }


# =========================
# CALLBACK SUNO (WAJIB ADA)
# =========================
@app.post("/callback/suno")
async def callback_suno(request: Request):
    try:
        payload = await request.json()
    except Exception:
        return {"ok": True}

    items = (payload.get("data") or {}).get("data") or []
    if not items:
        return {"ok": True}

    conn = get_db()
    for item in items:
        conn.execute("""
            INSERT INTO audios (
                audio_id,
                title,
                tags,
                duration,
                audio_url,
                stream_audio_url,
                image_url,
                created_at
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
            item.get("id"),
            item.get("title"),
            item.get("tags"),
            item.get("duration"),
            item.get("audio_url"),
            item.get("stream_audio_url"),
            item.get("image_url"),
            datetime.utcnow().isoformat()
        ))
    conn.commit()
    conn.close()

    return {"success": True}


# =========================
# API ANDROID
# =========================
@app.get("/audios")
def list_audios():
    conn = get_db()
    rows = conn.execute("""
        SELECT audio_id, title, tags, duration,
               audio_url, stream_audio_url, image_url
        FROM audios
        ORDER BY id DESC
    """).fetchall()
    conn.close()

    return {
        "count": len(rows),
        "data": [dict(r) for r in rows]
    }


@app.get("/audio/{audio_id}")
def audio_detail(audio_id: str):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM audios WHERE audio_id=?",
        (audio_id,)
    ).fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Audio not found")

    return dict(row)
