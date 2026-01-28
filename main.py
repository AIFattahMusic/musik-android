import os
import requests
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from typing import Optional, List

# ======================
# CONFIG
# ======================

SUNO_TOKEN = os.getenv("SUNO_TOKEN")
if not SUNO_TOKEN:
    raise RuntimeError("SUNO_TOKEN belum diset")

SUNO_GENERATE_URL = "https://api.sunoapi.org/api/v1/generate"
SUNO_RECORD_INFO_URL = "https://api.sunoapi.org/api/v1/generate/record-info"

BASE_URL = "https://musik-android.onrender.com"  # ganti jika perlu

HEADERS = {
    "Authorization": f"Bearer {SUNO_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# ======================
# APP
# ======================

app = FastAPI(title="Suno Music API")

# Simpan hasil di memory (contoh)
TASKS: List[dict] = []
SONGS: List[dict] = []

# ======================
# MODELS
# ======================

class GenerateRequest(BaseModel):
    prompt: str
    tags: Optional[str] = None

# ======================
# ROUTES
# ======================

@app.get("/")
def root():
    return {"status": "ok"}

# ======================
# GENERATE MUSIC
# ======================

@app.post("/generate/full-song")
def generate_song(data: GenerateRequest):
    payload = {
        "prompt": data.prompt,
        "tags": data.tags or "",
        # ⛔ MODEL WAJIB untuk akun kamu
        "model": "chirp-v3",
        "callBackUrl": f"{BASE_URL}/callback",
    }

    try:
        r = requests.post(
            SUNO_GENERATE_URL,
            headers=HEADERS,
            json=payload,
            timeout=60,
        )
    except Exception as e:
        raise HTTPException(500, f"Gagal request ke Suno: {e}")

    if r.status_code != 200:
        raise HTTPException(r.status_code, r.text)

    resp = r.json()

    # biasanya berisi taskId / task_id
    TASKS.append(resp)
    return resp

# ======================
# CALLBACK SUNO
# ======================

@app.post("/callback")
async def suno_callback(request: Request):
    body = await request.json()

    code = body.get("code")
    msg = body.get("msg")
    data = body.get("data", {})

    task_id = data.get("task_id")
    callback_type = data.get("callbackType")
    music_list = data.get("data", [])

    print(
        f"Callback | task_id={task_id} | "
        f"type={callback_type} | code={code} | msg={msg}"
    )

    if code == 200 and callback_type == "complete":
        for music in music_list:
            SONGS.append({
                "task_id": task_id,
                "title": music.get("title"),
                "duration": music.get("duration"),
                "tags": music.get("tags"),
                "audio_url": music.get("audio_url"),
                "image_url": music.get("image_url"),
            })

    return {"status": "received"}

# ======================
# POLLING STATUS (OPSIONAL)
# ======================

@app.get("/status/{task_id}")
def check_status(task_id: str):
    params = {"taskId": task_id}

    try:
        r = requests.get(
            SUNO_RECORD_INFO_URL,
            headers=HEADERS,
            params=params,
            timeout=30,
        )
    except Exception as e:
        raise HTTPException(500, f"Gagal cek status Suno: {e}")

    if r.status_code != 200:
        raise HTTPException(r.status_code, r.text)

    return r.json()

# ======================
# GET SONGS
# ======================

@app.get("/songs")
def get_songs():
    return {
        "count": len(SONGS),
        "songs": SONGS
    }
