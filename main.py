from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
import requests
import os

app = FastAPI()

# ======================
# CONFIG
# ======================
API_URL_GENERATE = "https://api.sunoapi.org/api/v1/generate"
CALLBACK_URL = "https://musik-android.onrender.com/music/callback"

SAVE_DIR = "outputs"
os.makedirs(SAVE_DIR, exist_ok=True)

music_tasks = {}

# ======================
# MODELS
# ======================
class GenerateRequest(BaseModel):
    prompt: str
    style: str | None = None
    title: str | None = None
    vocalGender: str | None = None

# ======================
# HEADERS
# ======================
def get_headers():
    token = os.getenv("SUNO_TOKEN")
    if not token:
        print("❌ TOKEN TIDAK ADA")
        raise HTTPException(status_code=500, detail="SUNO_TOKEN belum diset")

    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

# ======================
# ROOT (TEST)
# ======================
@app.get("/")
def root():
    return {"status": "ok"}

# ======================
# DEBUG TOKEN
# ======================
@app.get("/debug/token")
def debug_token():
    return {"token_loaded": bool(os.getenv("SUNO_TOKEN"))}

# ======================
# GENERATE MUSIC
# ======================
@app.post("/music/generate")
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

    print("➡️ PAYLOAD:", payload)

    response = requests.post(
        API_URL_GENERATE,
        json=payload,
        headers=headers,
        timeout=30
    )

    print("⬅️ STATUS:", response.status_code)
    print("⬅️ BODY:", response.text)

    if response.status_code != 200:
        raise HTTPException(
            status_code=500,
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
            detail=f"Tidak ada taskId dari API: {data}"
        )

    music_tasks[task_id] = {
        "status": "PENDING"
    }

    return {
        "success": True,
        "taskId": task_id,
        "status": "PENDING"
    }

# ======================
# CHECK STATUS
# ======================
@app.get("/music/status/{task_id}")
def check_status(task_id: str):
    task = music_tasks.get(task_id)
    if not task:
        raise HTTPException(404, "Task ID tidak ditemukan")

    return {
        "taskId": task_id,
        **task
    }

# ======================
# CALLBACK
# ======================
@app.post("/music/callback")
async def music_callback(request: Request):
    payload = await request.json()
    print("📥 CALLBACK:", payload)

    task_id = payload.get("taskId")
    if task_id:
        music_tasks[task_id] = payload

    return JSONResponse({"status": "ok"})        "defaultParamFlag": True,
        "audioId": body.audioId,
        "model": "V4_5ALL",
        "callBackUrl": CALLBACK_URL,
        "prompt": body.prompt or "Extend the music smoothly",
        "title": body.title or "Extended Music",
        "continueAt": body.continueAt,
        "styleWeight": 0.65,
        "audioWeight": 0.65,
        "weirdnessConstraint": 0.65
    

    response = requests.post(
        API_URL_EXTEND,
        json=payload,
        headers=headers,
        timeout=30
    )

    if response.status_code != 200:
        raise HTTPException(response.status_code, response.text)

    data = response.json()

    task_id = (
        data.get("taskId")
        or data.get("data", {}).get("taskId")
    )

    if not task_id:
        raise HTTPException(500, f"API tidak mengembalikan taskId: {data}")

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
@app.get("/music/status/{task_id}")
def check_status(task_id: str):
    task = music_tasks.get(task_id)
    if not task:
        raise HTTPException(404, "Task ID tidak ditemukan")

    return {
        "taskId": task_id,
        **task
    }

# ======================
# CALLBACK
# ======================
@app.post("/music/callback")
async def music_callback(request: Request):
    payload = await request.json()

    task_id = payload.get("taskId")
    if not task_id:
        return JSONResponse({"status": "ignored"})

    music_tasks[task_id] = payload
    return JSONResponse({"status": "ok"})

# ======================
# PLAY
# ======================
@app.get("/play/{task_id}")
def play(task_id: str):
    path = os.path.join(SAVE_DIR, task_id + ".mp3")
    if not os.path.exists(path):
        raise HTTPException(404, "Belum siap")

    return FileResponse(path, media_type="audio/mpeg")

# ======================
# DOWNLOAD
# ======================
@app.get("/download/{task_id}")
def download(task_id: str):
    path = os.path.join(SAVE_DIR, task_id + ".mp3")
    if not os.path.exists(path):
        raise HTTPException(404, "Belum siap")

    return FileResponse(path, filename=task_id + ".mp3")


