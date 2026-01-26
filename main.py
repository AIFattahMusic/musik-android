import os
import requests
from typing import Optional, Dict, Any

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
# ENV
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

if not SUNO_TOKEN:
    raise Exception("SUNO_TOKEN belum diisi (Render → Environment Variables)")

HEADERS = {
    "Authorization": f"Bearer {SUNO_TOKEN}",
    "Content-Type": "application/json"
}

# =========================
# STORAGE
# =========================
RESULTS: Dict[str, Any] = {}

# =========================
# REQUEST MODEL
# =========================
class GenerateRequest(BaseModel):
    mv: str = "sonic-v4-5"
    custom_mode: bool = False
    gpt_description_prompt: str
    tags: Optional[str] = ""

# =========================
# ENDPOINT: GENERATE SONG
# =========================
@app.post("/generate/full-song")
def generate_full_song(data: GenerateRequest):
    payload = {
        "mv": data.mv,
        "custom_mode": data.custom_mode,
        "gpt_description_prompt": data.gpt_description_prompt,
        "tags": data.tags,
    }

    try:
        r = requests.post(
            SUNO_API_CREATE_URL,
            headers=HEADERS,
            json=payload,
            timeout=60
        )

        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=r.text)

        return r.json()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =========================
# ENDPOINT: STATUS
# =========================
@app.get("/generate/status/{task_id}")
def generate_status(task_id: str):
    r = requests.get(
        f"{SUNO_API_STATUS_URL}/{task_id}",
        headers=HEADERS,
        timeout=30
    )

    if r.status_code != 200:
        raise HTTPException(status_code=404, detail=r.text)

    res = r.json()
    data = res.get("data", [])

    if not data:
        return {"status": "processing", "result": res}

    item = data[0]
    state = item.get("state") or item.get("status")
    audio_url = item.get("audio_url") or item.get("audioUrl") or item.get("audio")

    if state == "succeeded" and audio_url:
        return {"status": "done", "audio_url": audio_url}

    return {"status": "processing", "result": item}

# =========================
# DATABASE TEST
# =========================
def get_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])

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
