import os
import time
import requests
from typing import Optional, Dict, Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# =========================
# ENV
# =========================
SUNO_API_URL = os.getenv("SUNO_API_URL", "https://api.sunoapi.org/api/v1/generate")
SUNO_TOKEN = os.getenv("SUNO_TOKEN")

# Base URL backend kamu (Render)
BASE_URL = os.getenv("BASE_URL", "https://musik-android.onrender.com")
CALLBACK_URL = f"{BASE_URL}/panggilan_balik"

if not SUNO_TOKEN:
    raise Exception("SUNO_TOKEN belum diisi. Set di Render -> Environment Variables")

# =========================
# In-memory storage
# =========================
RESULTS: Dict[str, Any] = {}  # simpan callback berdasarkan taskId
LATEST_TASK_ID: Optional[str] = None


# =========================
# Request Model
# =========================
class GenerateRequest(BaseModel):
    mv: str = "sonic-v4-5"
    custom_mode: bool = False
    gpt_description_prompt: str
    tags: Optional[str] = ""

# =========================
# ENDPOINT 1: GENERATE FULL SONG
# =========================
@app.post("/generate/full-song")
def generate_full_song(data: GenerateRequest):
    payload = {
        "mv": data.mv,
        "custom_mode": data.custom_mode,
        "gpt_description_prompt": data.gpt_description_prompt,
        "tags": data.tags
    }

    try:
        r = requests.post(SUNO_API_CREATE_URL, headers=HEADERS, json=payload, timeout=60)

        # kalau error dari SunobdAPI, tampilkan jelas
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=r.text)

        return r.json()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =========================
# ENDPOINT 2: CEK STATUS TASK
# =========================
@app.get("/generate/status/{task_id}")
def generate_status(task_id: str):
    r = requests.get(f"{SUNOCAPI_STATUS_URL}/{task_id}", headers=HEADERS)

    if r.status_code != 200:
        raise HTTPException(status_code=404, detail=r.text)

    res = r.json()

    # ambil data item pertama
    item = None
    if isinstance(res.get("data"), list) and len(res["data"]) > 0:
        item = res["data"][0]

    if not item:
        return {"status": "processing", "result": res}

    state = item.get("state") or item.get("status")
    audio_url = item.get("audio_url") or item.get("audioUrl") or item.get("audio")

    # kalau sudah selesai dan ada audio
    if state == "succeeded" and audio_url:
        return {"status": "done", "audio_url": audio_url, "result": item}

    return {"status": "processing", "result": item}


import os, psycopg2

def get_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])
@app.get("/db-all")
def db_all():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT *
        FROM information_schema.tables
        WHERE table_schema = 'public';
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows




