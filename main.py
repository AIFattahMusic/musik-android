import os
import requests
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# =========================
# APP
# =========================
app = FastAPI(title="Suno Working API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# CONFIG
# =========================
BASE_URL = os.getenv(
    "BASE_URL",
    "https://musik-android.onrender.com"
).rstrip("/")

SUNO_TOKEN = os.getenv("SUNO_TOKEN")
if not SUNO_TOKEN:
    raise RuntimeError("SUNO_TOKEN belum diset")

SUNO_GENERATE_URL = "https://api.sunoapi.org/api/v1/generate"

HEADERS = {
    "Authorization": f"Bearer {SUNO_TOKEN}",
    "Content-Type": "application/json",
}

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
def health():
    return {"status": "ok"}

# =========================
# CALLBACK (WAJIB ADA)
# =========================
@app.post("/callback")
async def callback(req: Request):
    # Suno hanya butuh endpoint ini ADA
    return {"status": "received"}

# =========================
# GENERATE MUSIC (FIXED)
# =========================
@app.post("/generate")
def generate_music(data: GenerateRequest):
    payload = {
        "prompt": data.prompt,
        "tags": data.tags,
        "custom_mode": data.custom_mode,
        "instrumental": data.instrumental,
        "model": data.model,
        # ⛔ INI WAJIB
        "callBackUrl": f"{BASE_URL}/callback",
    }

    try:
        r = requests.post(
            SUNO_GENERATE_URL,
            headers=HEADERS,
            json=payload,
            timeout=60,
        )
    except requests.RequestException:
        raise HTTPException(502, "Tidak bisa konek ke Suno")

    # Suno suka balas 200 tapi code 400 di body
    res = r.json()
    if res.get("code") != 200:
        raise HTTPException(400, res.get("msg", "Generate gagal"))

    return res

# =========================
# STREAM / PLAY AUDIO
# =========================
@app.get("/play")
def play_audio(audio_url: str = Query(...)):
    try:
        r = requests.get(audio_url, stream=True, timeout=30)
    except requests.RequestException:
        raise HTTPException(502, "Gagal ambil audio")

    if r.status_code != 200:
        raise HTTPException(202, "Audio belum siap")

    return StreamingResponse(
        r.iter_content(chunk_size=8192),
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": "inline; filename=music.mp3"
        },
    )


