from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import psycopg2
import psycopg2.extras
import datetime
import os
import uvicorn

app = FastAPI(
    title="Music Android Backend",
    version="1.0.0"
)

# ======================================================
# DATABASE (RENDER POSTGRES)
# ======================================================
DATABASE_URL = os.environ.get("DATABASE_URL")
conn = psycopg2.connect(DATABASE_URL, sslmode="require")

def get_cursor():
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

# ======================================================
# INIT TABLE
# ======================================================
with get_cursor() as cur:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS songs (
            task_id TEXT PRIMARY KEY,
            title TEXT,
            audio_url TEXT,
            cover_url TEXT,
            lyrics TEXT,
            status TEXT,
            created_at TIMESTAMP
        )
    """)
    conn.commit()

# ======================================================
# SCHEMAS (INI YANG BIKIN SWAGGER BENAR)
# ======================================================
class CreateSongRequest(BaseModel):
    task_id: str
    title: Optional[str] = "Untitled Song"
    lyrics: Optional[str] = None
    cover_url: Optional[str] = None

class UpdateCoverRequest(BaseModel):
    cover_url: str

# ======================================================
# HEALTH CHECK
# ======================================================
@app.get("/")
def root():
    return {"status": "alive"}

# ======================================================
# SUNO CALLBACK
# ======================================================
@app.post("/suno/callback")
async def suno_callback(request: Request):
    try:
        payload = await request.json()
        print("🔔 SUNO CALLBACK:", payload)

        callback_type = payload.get("callbackType")
        task_id = payload.get("task_id") or payload.get("id")

        audio_url = (
            payload.get("audio_url")
            or payload.get("data", {}).get("audio_url")
        )

        lyrics = (
            payload.get("lyrics")
            or payload.get("data", {}).get("lyrics")
        )

        if not task_id:
            return {"status": "ignored"}

        with get_cursor() as cur:
            cur.execute("""
                INSERT INTO songs (task_id, status, created_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (task_id) DO NOTHING
            """, (
                task_id,
                "processing",
                datetime.datetime.utcnow()
            ))

            if callback_type == "completed" and audio_url:
                cur.execute("""
                    UPDATE songs
                    SET audio_url=%s,
                        lyrics=%s,
                        status=%s
                    WHERE task_id=%s
                """, (
                    audio_url,
                    lyrics,
                    "completed",
                    task_id
                ))

            conn.commit()

        print("✅ SONG COMPLETED:", task_id)
        return {"status": "ok"}

    except Exception as e:
        print("❌ CALLBACK ERROR:", str(e))
        return JSONResponse(
            status_code=200,
            content={"status": "error", "message": str(e)}
        )

# ======================================================
# CREATE SONG (ANDROID / SWAGGER)
# ======================================================
@app.post("/song/create")
async def create_song(data: CreateSongRequest):
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO songs
            (task_id, title, cover_url, lyrics, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (task_id) DO NOTHING
        """, (
            data.task_id,
            data.title,
            data.cover_url,
            data.lyrics,
            "processing",
            datetime.datetime.utcnow()
        ))
        conn.commit()

    return {
        "task_id": data.task_id,
        "status": "processing"
    }

# ======================================================
# GET SONG (ANDROID POLLING)
# ======================================================
@app.get("/song/{task_id}")
def get_song(task_id: str):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM songs WHERE task_id=%s", (task_id,))
        song = cur.fetchone()

    if not song:
        return JSONResponse(
            status_code=404,
            content={"error": "song not found"}
        )

    return song

# ======================================================
# LIST SONGS
# ======================================================
@app.get("/songs")
def list_songs():
    with get_cursor() as cur:
        cur.execute("""
            SELECT * FROM songs
            ORDER BY created_at DESC
        """)
        return cur.fetchall()

# ======================================================
# UPDATE COVER ART
# ======================================================
@app.post("/song/{task_id}/cover")
async def update_cover(task_id: str, data: UpdateCoverRequest):
    with get_cursor() as cur:
        cur.execute("""
            UPDATE songs
            SET cover_url=%s
            WHERE task_id=%s
        """, (data.cover_url, task_id))
        conn.commit()

    return {"status": "updated"}

# ======================================================
# RENDER ENTRYPOINT
# ======================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port
    )
