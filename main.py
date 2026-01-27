import os
import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

# =========================
# APP
# =========================
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # jika pakai credentials → ganti domain spesifik
    allow_credentials=False,      # FIX: tidak boleh True jika origins "*"
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# BASE URL (PUBLIC)
# =========================
BASE_URL = os.getenv(
    "BASE_URL",
    "https://musik-android.onrender.com"
).rstrip("/")

# =========================
# SUNO CONFIG
# =========================
SUNO_API_CREATE_URL = "https://api.sunoapi.org/api/v1/generate"
SUNO_API_STATUS_URL = "https://api.sunoapi.org/api/v1/status"
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
# HEALTH
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
        # FIX: penamaan callbackUrl
        "callbackUrl": f"{BASE_URL}/generate/callback",
    }

    try:
        r = requests.post(
            SUNO_API_CREATE_URL,
            headers=HEADERS,
            json=payload,
            timeout=60,
        )
    except requests.RequestException as e:
        raise HTTPException(502, str(e))

    if r.status_code != 200:
        raise HTTPException(r.status_code, r.text)

    return r.json()

# =========================
# CALLBACK (WAJIB ADA)
# =========================
@app.post("/generate/callback")
async def generate_callback(req: Request):
    payload = await req.json()
    # optional: simpan log jika mau
    return {"status": "received"}

# =========================
# STATUS + AUTO DOWNLOAD
# =========================
@app.get("/generate/status/{task_id}")
def generate_status(task_id: str):
    if not task_id:
        raise HTTPException(400, "task_id tidak valid")

    mp3_path = f"{GENERATED_DIR}/{task_id}.mp3"

    # Jika sudah ada file
    if os.path.exists(mp3_path):
        return {
            "status": "done",
            "download_url": f"{BASE_URL}/generate/download/{task_id}",
        }

    try:
        r = requests.get(
            f"{SUNO_API_STATUS_URL}/{task_id}",
            headers=HEADERS,
            timeout=30,
        )
    except requests.RequestException as e:
        raise HTTPException(502, str(e))

    if r.status_code != 200:
        raise HTTPException(500, r.text)

    res = r.json()
    data = res.get("data") or []

    if not data:
        return {"status": "processing"}

    item = data[0]

    state = (
        item.get("state")
        or item.get("status")
        or ""
    ).lower()

    audio_url = (
        item.get("audio_url")
        or item.get("audioUrl")
        or item.get("audio")
    )

    # SUCCESS → download MP3
    if state in {"success", "succeeded", "done"} and audio_url:
        audio_resp = requests.get(audio_url, timeout=60)
        if audio_resp.status_code != 200:
            raise HTTPException(500, "Gagal download audio")

        with open(mp3_path, "wb") as f:
            f.write(audio_resp.content)

        return {
            "status": "done",
            "download_url": f"{BASE_URL}/generate/download/{task_id}",
        }

    if state in {"fail", "failed", "error"}:
        return {"status": "failed"}

    return {
        "status": "processing",
        "raw_state": state,
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
        filename=f"{task_id}.mp3",
    )
