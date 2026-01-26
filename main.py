import os
import requests
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psycopg2

# =========================
# APP
# =========================
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# ENV (AMAN UNTUK STARTUP)
# =========================
SUNO_API_CREATE_URL = os.getenv(
    "SUNO_API_CREATE_URL",
    "https://api.sunoapi.org/api/v1/generate"
)
SUNO_API_STATUS_URL = os.getenv(
    "SUNO_API_STATUS_URL",
    "https://api.sunoapi.org/api/v1/status"
)
SUNO_TOKEN = os.getenv("SUNO_TOKEN")

HEADERS = {
    "Authorization": f"Bearer {SUNO_TOKEN}" if SUNO_TOKEN else "",
    "Content-Type": "application/json",
}

# =========================
# REQUEST MODEL (KONSISTEN)
# =========================
class GenerateRequest(BaseModel):
    prompt: str
    tags: str = ""
    custom_mode: bool = False
    instrumental: bool = False
    model: str = "V4_5"

# =========================
# HEALTH CHECK (WAJIB)
# =========================
@app.get("/")
def root():
    return {"status": "ok"}

# =========================
# GENERATE SONG
# =========================
@app.post("/generate/full-song")
def generate_full_song(data: GenerateRequest):
    if not SUNO_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="SUNO_TOKEN belum diset di Render Environment Variables"
        )

    payload = {
        "prompt": data.prompt,
        "tags": data.tags,
        "custom_mode": data.custom_mode,
        "instrumental": data.instrumental,
        "model": data.model,
    }

    try:
        r = requests.post(
            SUNO_API_CREATE_URL,
            headers=HEADERS,
            json=payload,
            timeout=60,
        )

        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=r.text)

        return r.json()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =========================
# STATUS
# =========================
@app.get("/generate/status/{task_id}")
def generate_status(task_id: str):
    if not SUNO_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="SUNO_TOKEN belum diset di Render Environment Variables"
        )

    r = requests.get(
        f"{SUNO_API_STATUS_URL}/{task_id}",
        headers=HEADERS,
        timeout=30,
    )

    if r.status_code != 200:
        raise HTTPException(status_code=404, detail=r.text)

    res = r.json()
    data = res.get("data", [])

    if not data:
        return {"status": "processing"}

    item = data[0]
    state = item.get("state") or item.get("status")
    audio_url = (
        item.get("audio_url")
        or item.get("audioUrl")
        or item.get("audio")
    )

    if state == "succeeded" and audio_url:
        return {"status": "done", "audio_url": audio_url}

    return {"status": "processing", "result": item}

# =========================
# DATABASE (AMAN)
# =========================
def get_conn():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise HTTPException(
            status_code=500,
            detail="DATABASE_URL belum diset"
        )
    return psycopg2.connect(db_url)

@app.get("/db-all")
def db_all():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public';
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows
