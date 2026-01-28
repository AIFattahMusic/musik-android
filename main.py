from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
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

music_tasks: dict[str, dict] = {}

# ======================
# MODELS
# ======================
class GenerateRequest(BaseModel):
    prompt: str
    style: str | None = None
    title: str | None = None
    vocal_gender: str | None = Field(default=None, alias="vocalGender")

    class Config:
        populate_by_name = True


# ======================
# HEADERS
# ======================
def get_headers():
    token = os.getenv("SUNO_TOKEN")
    if not token:
        raise HTTPException(500, "SUNO_TOKEN belum diset")

    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }


# ======================
# ROOT
# ======================
@app.get("/")
def root():
    return {"status": "ok"}


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
        "vocalGender": body.vocal_gender,
        "model": "V4_5ALL",
        "callBackUrl": CALLBACK_URL
    }

    print("➡️ GENERATE PAYLOAD:", payload)

    response = requests.post(
        API_URL_GENERATE,
        json=payload,
        headers=headers,
        timeout=30
    )

    print("⬅️ STATUS:", response.status_code)
    print("⬅️ BODY:", response.text)

    if response.status_code != 200:
        raise HTTPException(502, response.text)

    data = response.json()
    task_id = data.get("taskId") or data.get("data", {}).get("taskId")

    if not task_id:
        raise HTTPException(500, f"Tidak ada taskId: {data}")

    music_tasks[task_id] = {"status": "PENDING"}

    return {
        "success": True,
        "taskId": task_id,
        "status": "PENDING"
    }


# ======================
# CALLBACK (PALING PENTING)
# ======================
@app.post("/music/callback")
async def music_callback(request: Request):
    payload = await request.json()
    print("📦 CALLBACK:", payload)

    task_id = payload.get("taskId")
    audio_url = payload.get("audioUrl") or payload.get("data", {}).get("audioUrl")

    if not task_id or not audio_url:
        raise HTTPException(400, "Callback tidak valid")

    # download audio
    audio_response = requests.get(audio_url, timeout=60)
    if audio_response.status_code != 200:
        raise HTTPException(500, "Gagal download audio")

    path = os.path.join(SAVE_DIR, f"{task_id}.mp3")
    with open(path, "wb") as f:
        f.write(audio_response.content)

    music_tasks[task_id] = {
        "status": "DONE",
        "audioUrl": audio_url,
        "file": path
    }

    return {"ok": True}


# ======================
# CHECK STATUS
# ======================
@app.get("/music/status/{task_id}")
def check_status(task_id: str):
    task = music_tasks.get(task_id)
    if not task:
        raise HTTPException(404, "Task ID tidak ditemukan")

    return {"taskId": task_id, **task}


# ======================
# PLAY
# ======================
@app.get("/play/{task_id}")
def play(task_id: str):
    path = os.path.join(SAVE_DIR, f"{task_id}.mp3")
    if not os.path.exists(path):
        raise HTTPException(404, "Audio belum siap")

    return FileResponse(path, media_type="audio/mpeg")


# ======================
# DOWNLOAD
# ======================
@app.get("/download/{task_id}")
def download(task_id: str):
    path = os.path.join(SAVE_DIR, f"{task_id}.mp3")
    if not os.path.exists(path):
        raise HTTPException(404, "Audio belum siap")

    return FileResponse(path, filename=f"{task_id}.mp3")    }

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
@ app.post("/music/callback")
async def music_callback(request: Request):
    payload = await request.json()
    print("📦 CALLBACK:", payload)

    task_id = payload.get("taskId")
    if task_id:
        music_tasks[task_id] = payload

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
        raise HTTPException(500, "API tidak mengembalikan taskId")

    music_tasks[task_id] = {
        "status": "PENDING",
        "audioUrl": None,
    }

    return {"ok": True}

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








