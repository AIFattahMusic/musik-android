import os
import httpx
import requests
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging
from supabase import create_client

# ==================================================
# SUPABASE CONFIG
# ==================================================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("SUPABASE ENV belum di-set!")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==================================================
# SUNO CONFIG
# ==================================================
SUNO_API_KEY = os.getenv("SUNO_API_KEY")

BASE_URL = os.getenv(
    "BASE_URL",
    "https://musik-android.onrender.com"
)

CALLBACK_URL = f"{BASE_URL}/callback"

SUNO_BASE_API = "https://api.kie.ai/api/v1"
MUSIC_GENERATE_URL = f"{SUNO_BASE_API}/generate"
STATUS_URL = f"{SUNO_BASE_API}/generate/record-info"

# ==================================================
# APP INIT
# ==================================================
app = FastAPI(
    title="AI Music Suno API Wrapper",
    version="5.0.0"
)

logging.basicConfig(level=logging.INFO)

# ==================================================
# MODEL
# ==================================================
class GenerateMusicRequest(BaseModel):
    prompt: str
    style: Optional[str] = None
    title: Optional[str] = None
    instrumental: bool = False
    customMode: bool = False
    model: str = "V4_5"

# ==================================================
# HELPERS
# ==================================================
def suno_headers():
    if not SUNO_API_KEY:
        raise HTTPException(status_code=500, detail="SUNO_API_KEY belum diatur!")
    return {
        "Authorization": f"Bearer {SUNO_API_KEY}",
        "Content-Type": "application/json"
    }

def simpan_hasil_lagu(task_id, title, prompt, audio_url, cover_url, lyrics, duration):

    # download audio
    audio_file = requests.get(audio_url, timeout=60).content
    supabase.storage.from_("audio").upload(
        f"{task_id}.mp3",
        audio_file,
        {"content-type": "audio/mpeg"}
    )

    # download cover jika ada
    if cover_url:
        cover_file = requests.get(cover_url, timeout=60).content
        supabase.storage.from_("covers").upload(
            f"{task_id}.jpg",
            cover_file,
            {"content-type": "image/jpeg"}
        )

    # insert metadata
    supabase.table("songs").insert({
        "task_id": task_id,
        "title": title,
        "prompt": prompt,
        "status": "completed",
        "audio_path": f"audio/{task_id}.mp3",
        "cover_path": f"covers/{task_id}.jpg" if cover_url else None,
        "lyrics": lyrics,
        "duration": duration
    }).execute()

# ==================================================
# ROOT
# ==================================================
@app.get("/")
def root():
    return {"status": "running", "version": "5.0.0"}

# ==================================================
# GENERATE
# ==================================================
@app.post("/generate-music")
async def generate_music(payload: GenerateMusicRequest):

    body = {
        "prompt": payload.prompt,
        "customMode": payload.customMode,
        "instrumental": payload.instrumental,
        "model": payload.model,
        "callBackUrl": CALLBACK_URL
    }

    if payload.style:
        body["style"] = payload.style
    if payload.title:
        body["title"] = payload.title

    async with httpx.AsyncClient(timeout=60) as client:
        res = await client.post(
            MUSIC_GENERATE_URL,
            headers=suno_headers(),
            json=body
        )

    res.raise_for_status()
    return res.json()

# ==================================================
# STATUS (AUTO SAVE + DONE)
# ==================================================
@app.get("/generate/status/{task_id}")
def generate_status(task_id: str):

    try:
        r = requests.get(
            STATUS_URL,
            headers=suno_headers(),
            params={"taskId": task_id},
            timeout=30
        )
        r.raise_for_status()
    except Exception:
        return {"status": "processing"}

    res = r.json()
    item = res.get("data")

    if isinstance(item, list) and len(item) > 0:
        item = item[0]

    if not item:
        return {"status": "processing"}

    state = item.get("state") or item.get("status")

    if state != "succeeded":
        return {"status": "processing"}

    audio_url = item.get("streamAudioUrl")
    cover_url = item.get("image_url")
    title = item.get("title")
    prompt = item.get("prompt")
    lyrics = item.get("prompt")
    duration = item.get("duration")

    if not audio_url:
        return {"status": "processing"}

    # cek sudah ada di DB belum
    existing = supabase.table("songs") \
        .select("task_id") \
        .eq("task_id", task_id) \
        .execute()

    if not existing.data:
        simpan_hasil_lagu(
            task_id,
            title,
            prompt,
            audio_url,
            cover_url,
            lyrics,
            duration
        )

    public_audio_url = f"{SUPABASE_URL}/storage/v1/object/public/audio/{task_id}.mp3"
    public_cover_url = f"{SUPABASE_URL}/storage/v1/object/public/covers/{task_id}.jpg" if cover_url else None

    return {
        "status": "done",
        "audio_url": public_audio_url,
        "image_url": public_cover_url,
        "duration": duration,
        "title": title,
        "lyrics": lyrics
    }

# ==================================================
# CALLBACK
# ==================================================
@app.post("/callback")
async def callback(request: Request):
    data = await request.json()
    logging.info(f"CALLBACK: {data}")
    return {"ok": True}
