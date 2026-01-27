from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import requests
import os

app = FastAPI()

# ======================
# CONFIG
# ======================
SUNO_API_URL_GENERATE = "https://api.sunoapi.org/api/v1/generate"
SUNO_API_URL_EXTEND = "https://api.sunoapi.org/api/v1/generate/extend"
CALLBACK_URL = "https://musik-android.onrender.com/suno/callback"

# 🔥 FALLBACK TOKEN (INI KUNCI)
SUNO_API_TOKEN = (
    os.getenv("SUNO_API_TOKEN")
    or os.getenv("SUNO_TOKEN")
)

def get_headers():
    if not SUNO_API_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="SUNO_API_TOKEN belum terbaca di environment"
        )

    return {
        "Authorization": f"Bearer {SUNO_API_TOKEN}",
        "Content-Type": "application/json"
    }

# ======================
# IN-MEMORY DB
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
# HEALTH CHECK
# ======================
@app.get("/")
def health():
    return {
        "status": "ok",
        "token_loaded": bool(SUNO_API_TOKEN)
    }

# ======================
# GENERATE MUSIC (BARU)
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
        SUNO_API_URL_GENERATE,
        json=payload,
        headers=headers,
        timeout=30
    )

    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code,
            detail=response.text
        )

    data = response.json()

task_id = (
    data.get("taskId")
    or data.get("data", {}).get("taskId")
)

if not task_id:
    raise HTTPException(
        status_code=500,
        detail=f"Suno tidak mengembalikan taskId: {data}"
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
# EXTEND MUSIC
# ======================
@app.post("/suno/extend")
def extend_music(body: ExtendRequest):
    headers = get_headers()

    payload = {
        "defaultParamFlag": True,
        "audioId": body.audioId,
        "model": "V4_5ALL",
        "callBackUrl": CALLBACK_URL,
        "prompt": body.prompt or "Extend the music smoothly",
        "title": body.title or "Extended Music",
        "continueAt": body.continueAt,
        "styleWeight": 0.65,
        "audioWeight": 0.65,
        "weirdnessConstraint": 0.65
    }

    response = requests.post(
        SUNO_API_URL_EXTEND,
        json=payload,
        headers=headers,
        timeout=30
    )

    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code,
            detail=response.text
        )

    data = response.json()
    task_id = data.get("taskId")

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
# CHECK STATUS
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
# CALLBACK
# ======================
@app.post("/suno/callback")
async def suno_callback(request: Request):
    payload = await request.json()

    print("=== SUNO CALLBACK ===")
    print(payload)

    task_id = payload.get("taskId")

    if task_id not in music_tasks:
        music_tasks[task_id] = payload
    conn.commit()
    conn.close()

# =====================
# CALLBACK
# =====================
@app.post("/generate-music-callback")
async def callback(request: Request):
    payload = await request.json()

    if payload.get("code") == 200:
        data = payload.get("data", {})
        if data.get("callbackType") == "complete":
            threading.Thread(
                target=download_audio,
                args=(data.get("task_id"), data.get("data", [])),
                daemon=True
            ).start()

    return JSONResponse({"status": "ok"})

# =====================
# PLAY
# =====================
@app.get("/play/{task_id}")
def play(task_id: str):
    path = os.path.join(SAVE_DIR, task_id + ".mp3")
    if not os.path.exists(path):
        raise HTTPException(404, "Belum siap")

    return FileResponse(path, media_type="audio/mpeg")

# =====================
# DOWNLOAD
# =====================
@app.get("/download/{task_id}")
def download(task_id: str):
    path = os.path.join(SAVE_DIR, task_id + ".mp3")
    if not os.path.exists(path):
        raise HTTPException(404, "Belum siap")

    return FileResponse(path, filename=task_id + ".mp3")











