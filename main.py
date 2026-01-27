import os
import sqlite3
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="Musik Android API")

# =========================
# Render Disk Path (PENTING)
# =========================
DB_PATH = "/data/musik.db"  # Render persistent disk


def init_db():
    os.makedirs("/data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS audio_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT,
            audio_id TEXT UNIQUE,
            title TEXT,
            tags TEXT,
            duration REAL,
            audio_url TEXT,
            stream_audio_url TEXT,
            image_url TEXT,
            model_name TEXT,
            prompt TEXT,
            create_time TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()


init_db()


# =========================
# Health Check (WAJIB)
# =========================
@app.get("/")
def health():
    return {"status": "ok", "platform": "render"}


# =========================
# Callback Endpoint
# =========================
@app.post("/callback")
async def callback(request: Request):
    try:
        payload = await request.json()

        # Render-friendly: cepat, tidak validasi berat
        if payload.get("code") != 200:
            return JSONResponse(status_code=200, content={"ok": True})

        data = payload.get("data", {})
        if data.get("callbackType") != "complete":
            return JSONResponse(status_code=200, content={"ok": True})

        task_id = data.get("task_id")
        results = data.get("data", [])

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        for item in results:
            cur.execute("""
                INSERT OR REPLACE INTO audio_results (
                    task_id,
                    audio_id,
                    title,
                    tags,
                    duration,
                    audio_url,
                    stream_audio_url,
                    image_url,
                    model_name,
                    prompt,
                    create_time,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task_id,
                item.get("id"),
                item.get("title"),
                item.get("tags"),
                item.get("duration"),
                item.get("audio_url"),
                item.get("stream_audio_url"),
                item.get("image_url"),
                item.get("model_name"),
                item.get("prompt"),
                item.get("createTime"),
                datetime.utcnow().isoformat()
            ))

        conn.commit()
        conn.close()

        return JSONResponse(status_code=200, content={"success": True})

    except Exception as e:
        print("Callback error:", e)
        return JSONResponse(status_code=200, content={"success": False})


# =========================
# API Android (List Audio)
# =========================
@app.get("/audios")
def audios():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT audio_id, title, tags, duration, audio_url, stream_audio_url, image_url
        FROM audio_results
        ORDER BY id DESC
    """)
    rows = cur.fetchall()
    conn.close()

    return {
        "count": len(rows),
        "data": [
            {
                "audio_id": r[0],
                "title": r[1],
                "tags": r[2],
                "duration": r[3],
                "audio_url": r[4],
                "stream_audio_url": r[5],
                "image_url": r[6]
            } for r in rows
        ]
    }


