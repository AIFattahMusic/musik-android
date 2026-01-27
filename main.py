import os
import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# =========================
# APP
# =========================
app = FastAPI(title="Suno Stable Proxy API")

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
# GENERATE MUSIC (NO LOGIC)
# =========================
@app.post("/generate")
def generate_music(data: GenerateRequest):
    """
    HANYA:
    - kirim request ke Suno
    - balikin response apa adanya
    """
    try:
        r = requests.post(
            SUNO_GENERATE_URL,
            headers=HEADERS,
            json={
                "prompt": data.prompt,
                "tags": data.tags,
                "custom_mode": data.custom_mode,
                "instrumental": data.instrumental,
                "model": data.model,
            },
            timeout=60,
        )
    except requests.RequestException:
        raise HTTPException(502, "Tidak bisa konek ke Suno")

    if r.status_code != 200:
        raise HTTPException(502, "Generate gagal")

    # ⚠️ JANGAN DIPARSE, JANGAN DIUTAK-ATIK
    return r.json()

# =========================
# STREAM / DOWNLOAD AUDIO
# =========================
@app.get("/play")
def play_audio(
    audio_url: str = Query(..., description="audioUrl dari Suno")
):
    """
    Proxy audio dari Suno.
    - Bisa diputar
    - Bisa di-download
    - Aman
    """
    try:
        r = requests.get(audio_url, stream=True, timeout=30)
    except requests.RequestException:
        raise HTTPException(502, "Gagal ambil audio")

    if r.status_code != 200:
        # BELUM SIAP = BUKAN ERROR FATAL
        raise HTTPException(202, "Audio belum siap, coba lagi")

    return StreamingResponse(
        r.iter_content(chunk_size=8192),
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": "inline; filename=music.mp3"
        }
    )
