from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import httpx
import os
from typing import Dict

# ======================
# CONFIG
# ======================
API_URL_GENERATE = "https://api.sunoapi.org/api/v1/generate"
CALLBACK_URL = "https://musik-android.onrender.com/music/callback"

SAVE_DIR = "outputs"
os.makedirs(SAVE_DIR, exist_ok=True)

SUNO_TOKEN = os.getenv("SUNO_TOKEN")
CALLBACK_SECRET = os.getenv("CALLBACK_SECRET", "secret123")

if not SUNO_TOKEN:
    raise RuntimeError("SUNO_TOKEN belum diset")

# taskId -> status
music_tasks: Dict[str, dict] = {}

app = FastAPI()

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
    return {
        "Authorization": f"Bearer {SUNO_TOKEN}",
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
async def generate_music(body: GenerateRequest):
    payload = {
        "prompt": body.prompt,
        "style": body.style,
        "title": body.title,
        "vocalGender": body.vocal_gender,
        "model": "V4_5ALL",
        "callBackUrl": CALLBACK_URL,
        "callbackSecret": CALLBACK_SECRET
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            API_URL_GENERATE,
            json=payload,
            headers=get_headers()
        )

    if not resp.ok:
        raise HTTPException(502, resp.text)

    data = resp.json()
    task_id = data.get("taskId") or data.get("data", {}).get("taskId")

    if not task_id:
        raise HTTPException(500, f"Tidak ada taskId: {data}")

    music_tasks[task_id] = {"status": "PENDING"}

    return {"success": True, "taskId": task_id}

# ======================
# CALLBACK
# ======================
@app.post("/music/callback")
async def music_callback(request: Request):
    payload = await request.json()

    # Proteksi callback
    if payload.get("callbackSecret") != CALLBACK_SECRET:
        raise HTTPException(403, "Callback tidak valid")

    task_id = payload.get("taskId")
    audio_url = (
        payload.get("audioUrl")
        or payload.get("data", {}).get("audioUrl")
    )

    if not task_id or not audio_url:
        raise HTTPException(400, "Payload callback tidak lengkap")

    path = os.path.join(SAVE_DIR, f"{task_id}.mp3")

    # Idempotent (kalau callback retry)
    if os.path.exists(path):
        music_tasks[task_id] = {
            "status": "DONE",
            "audioUrl": audio_url
        }
        return {"ok": True}

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            audio = await client.get(audio_url)

        if not audio.ok:
            raise HTTPException(500, "Gagal download audio")

        with open(path, "wb") as f:
            f.write(audio.content)

    except Exception as e:
        raise HTTPException(500, str(e))

    music_tasks[task_id] = {
        "status": "DONE",
        "audioUrl": audio_url
    }

    return {"ok": True}

# ======================
# CHECK STATUS
# ======================
@app.get("/music/status/{task_id}")
def check_status(task_id: str):
    task = music_tasks.get(task_id)

    path = os.path.join(SAVE_DIR, f"{task_id}.mp3")
    if not task and os.path.exists(path):
        return {"taskId": task_id, "status": "DONE"}

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

    return FileResponse(path, filename=f"{task_id}.mp3")        raise HTTPException(500, "Gagal download audio")

    path = os.path.join(SAVE_DIR, f"{task_id}.mp3")
    with open(path, "wb") as f:
        f.write(audio.content)

    music_tasks[task_id] = {
        "status": "DONE",
        "audioUrl": audio_url
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

    return FileResponse(path, filename=f"{task_id}.mp3")    return FileResponse(path, media_type="audio/mpeg")


@app.get("/download/{task_id}")
def download(task_id: str):
    path = os.path.join(SAVE_DIR, f"{task_id}.mp3")
    if not os.path.exists(path):
        raise HTTPException(404, "Audio belum siap")

    return FileResponse(path, filename=f"{task_id}.mp3")    payload = await request.json()
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











