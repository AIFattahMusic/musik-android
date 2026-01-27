from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import requests
import os
import time

app = FastAPI()

# ======================
# CONFIG
# ======================
SUNO_GENERATE_URL = "https://api.sunoapi.org/api/v1/generate"
SUNO_EXTEND_URL = "https://api.sunoapi.org/api/v1/generate/extend"
CALLBACK_URL = "https://musik-android.onrender.com/suno/callback"

SUNO_API_TOKEN = (
    os.getenv("SUNO_API_TOKEN")
    or os.getenv("SUNO_TOKEN")
)

def get_headers():
    if not SUNO_API_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="SUNO_API_TOKEN tidak terbaca"
        )
    return {
        "Authorization": f"Bearer {SUNO_API_TOKEN}",
        "Content-Type": "application/json"
    }

# ======================
# MEMORY STORE
# ======================
# NOTE: Render restart = data hilang
music_tasks = {}

# ======================
# SCHEMA
# ======================
class GenerateRequest(BaseModel):
    prompt: str
    style: str | None = "Pop"
    title: str | None = "My Song"
    vocalGender: str | None = None

class ExtendRequest(BaseModel):
    audioId: str
    continueAt: int = 60

# ======================
# HEALTH
# ======================
@app.get("/")
def health():
    return {
        "status": "ok",
        "token_loaded": bool(SUNO_API_TOKEN),
        "songs_saved": len(music_tasks)
    }

# ======================
# GENERATE MUSIC
# ======================
@app.post("/suno/generate")
def generate_music(body: GenerateRequest):
    headers = get_headers()

    payload = {
        "prompt": body.prompt,
        "style": body.style,
        "title": body.title,
        "vocalGender": body.vocalGender,
        "model": "V4_5ALL",
        "callBackUrl": CALLBACK_URL
    }

    response = requests.post(
        SUNO_GENERATE_URL,
        json=payload,
        headers=headers,
        timeout=30
    )

    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code,
            detail=response.text
        )

    # ⚠️ JANGAN CARI taskId DI SINI
    return {
        "success": True,
        "status": "PENDING",
        "message": "Generate dikirim. Menunggu callback Suno."
    }

# ======================
# EXTEND MUSIC
# ======================
@app.post("/suno/extend")
def extend_music(body: ExtendRequest):
    headers = get_headers()

    payload = {
        "defaultParamFlag": True,
        "audioId": body.audioId,
        "model": "V4_5ALL",
        "continueAt": body.continueAt,
        "callBackUrl": CALLBACK_URL
    }

    response = requests.post(
        SUNO_EXTEND_URL,
        json=payload,
        headers=headers,
        timeout=30
    )

    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code,
            detail=response.text
        )

    return {
        "success": True,
        "status": "PENDING",
        "message": "Extend dikirim. Menunggu callback Suno."
    }

# ======================
# CALLBACK (INI INTINYA)
# ======================
@app.post("/suno/callback")
async def suno_callback(request: Request):
    try:
        payload = await request.json()
    except Exception:
        return {"status": "ignored"}

    print("SUNO CALLBACK RAW:", payload)

    data = payload.get("data", {})
    task_id = data.get("task_id")

    if not task_id:
        return {"status": "no_task_id"}

    songs = data.get("data", [])
    if not songs:
        return {"status": "no_songs"}

    # simpan SEMUA lagu
    music_tasks[task_id] = {
        "status": "SUCCESS",
        "songs": []
    }

    for song in songs:
        music_tasks[task_id]["songs"].append({
            "audio_id": song.get("id"),
            "audio_url": song.get("audio_url"),
            "stream_url": song.get("stream_audio_url"),
            "image_url": song.get("image_url"),
            "title": song.get("title"),
            "prompt": song.get("prompt"),
            "duration": song.get("duration"),
            "model": song.get("model_name"),
            "created_at": song.get("createTime")
        })

    return {"status": "ok"}

# ======================
# GET ALL SONGS
# ======================
@app.get("/suno/all")
def get_all_songs():
    return music_tasks

# ======================
# GET SONG BY TASK
# ======================
@app.get("/suno/task/{task_id}")
def get_task(task_id: str):
    task = music_tasks.get(task_id)
    if not task:
        raise HTTPException(
            status_code=404,
            detail="Task tidak ditemukan"
        )
    return task
