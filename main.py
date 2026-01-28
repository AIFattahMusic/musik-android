import os
import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ======================
# APP
# ======================
app = FastAPI(title="Suno Music Render API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ======================
# CONFIG
# ======================
SUNO_API_URL = SUNO_API_URL = "https://api.sunoapi.org/api/v1/generate"
SUNO_TOKEN = os.getenv("SUNO_TOKEN")

BASE_URL = "https://musik-android.onrender.com"

HEADERS = {
    "Authorization": f"Bearer {SUNO_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# ======================
# DB SEDERHANA (RAM)
# ======================
DB = []

# ======================
# MODEL REQUEST
# ======================
class GenerateRequest(BaseModel):
    title: str
    prompt: str
    tags: str | None = None

# ======================
# HEALTH CHECK
# ======================
@app.get("/")
def root():
    return {"status": "ok"}

# ======================
# GENERATE SONG
# ======================
@app.post("/generate/full-song")
def generate_full_song(data: GenerateRequest):
    payload = {
        "title": data.title or "Untitled Song",
        "prompt": data.prompt or "Create a song",
        "tags": data.tags or "reggae",
        "customMode": False,
        "instrumental": False,
        "callbackUrl": f"{BASE_URL}/callback",
    }

    try:
        r = requests.post(
            SUNO_API_URL,
            headers=HEADERS,
            json=payload,
            timeout=60,
        )
    except requests.RequestException as e:
        raise HTTPException(502, f"Gagal koneksi ke Suno: {e}")

    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)

    return r.json()

# ======================
# CALLBACK SUNO
# ======================
@app.post("/callback")
async def callback(request: Request):
    body = await request.body()
    if not body:
        return {"ok": True}

    data = await request.json()

    if data.get("status") == "completed":
        DB.append({
            "task_id": data.get("id"),
            "title": data.get("title"),
            "audio_url": data.get("audio_url"),
            "image_url": data.get("image_url"),
        })

    return {"ok": True}

# ======================
# LIHAT ISI DB
# ======================
@app.get("/songs")
def list_songs():
    return DB


