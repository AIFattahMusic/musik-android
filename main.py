import os
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

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
# BASE URL (PUBLIC)
# =========================
BASE_URL = os.getenv(
    "BASE_URL",
    "https://musik-android.onrender.com"
)

# =========================
# SUNO CONFIG
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
    raise RuntimeError("SUNO_TOKEN belum diset")

HEADERS = {
    "Authorization": f"Bearer {SUNO_TOKEN}",
    "Content-Type": "application/json",
}

# =========================
# STORAGE
# =========================
GENERATED_DIR = "generated"
os.makedirs(GENERATED_DIR, exist_ok=True)

# =========================
# MODEL
# =========================
class GenerateRequest(BaseModel):
    prompt: str
    tags: str = ""
    custom_mode: bool = False
    instrumental: bool = False
    model: str = "V4_5"

# =========================
# HEALTH CHECK
# =========================
@app.get("/")
def root():
    return {"status": "ok"}

# =========================
# GENERATE SONG
# =========================
@app.post("/generate/full-song")
def generate_full_song(data: GenerateRequest):
    payload = {
        "prompt": data.prompt,
        "tags": data.tags,
        "custom_mode": data.custom_mode,
        "instrumental": data.instrumental,
        "model": data.model,
    }

    r = requests.post(
        SUNO_API_CREATE_URL,
        headers=HEADERS,
        json=payload,
        timeout=60,
    )

    if r.status_code != 200:
        raise HTTPException(r.status_code, r.text)

    return r.json()

# =========================
# STATUS + AUTO DOWNLOAD
# =========================
@app.get("/generate/status/{task_id}")
def generate_status(task_id: str):
    mp3_path = f"{GENERATED_DIR}/{task_id}.mp3"

    # Jika file sudah ada
    if os.path.exists(mp3_path):
        return {
            "status": "done",
            "download_url": f"{BASE_URL}/generate/download/{task_id}"
        }

    # Cek status ke Suno
    r = requests.get(
        f"{SUNO_API_STATUS_URL}/{task_id}",
        headers=HEADERS,
        timeout=30,
    )

    if r.status_code != 200:
        raise HTTPException(500, r.text)

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

    # SUCCESS → download MP3
    if state in ["SUCCESS", "succeeded", "done"] and audio_url:
        audio_resp = requests.get(audio_url, timeout=60)
        if audio_resp.status_code != 200:
            raise HTTPException(500, "Gagal download audio dari Suno")

        with open(mp3_path, "wb") as f:
            f.write(audio_resp.content)

        return {
            "status": "done",
            "download_url": f"{BASE_URL}/generate/download/{task_id}"
        }

    if state in ["FAIL", "FAILED", "error"]:
        return {"status": "failed"}

    return {
        "status": "processing",
        "raw_state": state
    }

# =========================
# DOWNLOAD MP3
# =========================
@app.get("/generate/download/{task_id}")
def download_mp3(task_id: str):
    path = f"{GENERATED_DIR}/{task_id}.mp3"

    if not os.path.exists(path):
        raise HTTPException(404, "File belum tersedia")

    return FileResponse(
        path,
        media_type="audio/mpeg",
        filename=f"{task_id}.mp3"
    )


