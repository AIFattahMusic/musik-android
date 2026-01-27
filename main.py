from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import requests
import os
import time

app = FastAPI()

# ======================
# CONFIG
# ======================
SUNO_API_URL_GENERATE = "https://api.sunoapi.org/api/v1/generate"
SUNO_API_URL_EXTEND = "https://api.sunoapi.org/api/v1/generate/extend"
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
# SIMPLE RATE LIMITER
# ======================
last_generate_time = 0

def rate_limit(seconds=60):
    global last_generate_time
    now = time.time()
    if now - last_generate_time < seconds:
        raise HTTPException(
            status_code=429,
            detail="Tunggu 1 menit sebelum generate lagi"
        )
    last_generate_time = now

# ======================
# MEMORY STORE
# ======================
music_tasks = {}

# ======================
# SCHEMAS
# ======================
class GenerateRequest(BaseModel):
    prompt: str
    style: str | None = "Pop"
    title: str | None = "My Song"
    vocalGender: str | None = None

class ExtendRequest(BaseModel):
    audioId: str
    continueAt: int = 60
    prompt: str | None = None
    title: str | None = None

# ======================
# HEALTH
# ======================
@app.get("/")
def health():
    return {
        "status": "ok",
        "token_loaded": bool(SUNO_API_TOKEN)
    }

# ======================
# GENERATE MUSIC (AMAN)
# ======================
@app.post("/suno/generate")
def generate_music(body: GenerateRequest):
    rate_limit(60)
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
        SUNO_API_URL_GENERATE,
        json=payload,
        headers=headers,
        timeout=30
    )

    data = response.json()

    # 🔥 AMBIL taskId DARI SEMUA KEMUNGKINAN
    task_id = (
        data.get("taskId")
        or data.get("data", {}).get("taskId")
        or data.get("data", {}).get("task", {}).get("taskId")
    )

    # ❌ JANGAN BOROS TOKEN
    if not task_id:
        print("SUNO RAW RESPONSE:", data)
        raise HTTPException(
            status_code=500,
            detail="taskId tidak ditemukan. Generate dihentikan."
        )

    music_tasks[task_id] = {
        "status": "PENDING",
        "audioUrl": None,
        "coverUrl": None,
        "duration": None
    }

    return {
        "success": True,
        "taskId": task_id,
        "status": "PENDING"
    }

# ======================
# EXTEND MUSIC (AMAN)
# ======================
@app.post("/suno/extend")
def extend_music(body: ExtendRequest):
    rate_limit(60)
    headers = get_headers()

    payload = {
        "defaultParamFlag": True,
        "audioId": body.audioId,
        "model": "V4_5ALL",
        "callBackUrl": CALLBACK_URL,
        "prompt": body.prompt or "Extend smoothly",
        "title": body.title or "Extended Music",
        "continueAt": body.continueAt
    }

    response = requests.post(
        SUNO_API_URL_EXTEND,
        json=payload,
        headers=headers,
        timeout=30
    )

    data = response.json()

    task_id = (
        data.get("taskId")
        or data.get("data", {}).get("taskId")
        or data.get("data", {}).get("task", {}).get("taskId")
    )

    if not task_id:
        print("SUNO RAW RESPONSE:", data)
        raise HTTPException(
            status_code=500,
            detail="taskId tidak ditemukan. Extend dihentikan."
        )

    music_tasks[task_id] = {
        "status": "PENDING",
        "audioUrl": None,
        "coverUrl": None,
        "duration": None
    }

    return {
        "success": True,
        "taskId": task_id,
        "status": "PENDING"
    }

# ======================
# CHECK STATUS (GRATIS)
# ======================
@app.get("/suno/status/{task_id}")
def check_status(task_id: str):
    task = music_tasks.get(task_id)
    if not task:
        raise HTTPException(
            status_code=404,
            detail="Task ID tidak ditemukan"
        )
    return {
        "taskId": task_id,
        **task
    }

# ======================
# CALLBACK (PENTING)
# ======================
@app.post("/suno/callback")
async def suno_callback(request: Request):
    payload = await request.json()

    print("SUNO CALLBACK:", payload)

    task_id = payload.get("taskId")
    if not task_id:
        return {"status": "ignored"}

    music_tasks.setdefault(task_id, {})
    music_tasks[task_id].update({
        "status": payload.get("status"),
        "audioUrl": payload.get("audioUrl"),
        "coverUrl": payload.get("coverUrl"),
        "duration": payload.get("duration")
    })

    return {"status": "ok"}
