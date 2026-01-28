from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import httpx
import os
from typing import Dict, List

# ======================
# CONFIG
# ======================
API_URL_GENERATE = "https://api.sunoapi.org/api/v1/generate"
CALLBACK_URL = "https://musik-android.onrender.com/music/callback"

SAVE_DIR = "outputs"
os.makedirs(SAVE_DIR, exist_ok=True)

SUNO_TOKEN = os.getenv("SUNO_TOKEN")
if not SUNO_TOKEN:
    raise RuntimeError("SUNO_TOKEN belum diset")

app = FastAPI()

# task_id -> status
music_tasks: Dict[str, dict] = {}

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
        "callBackUrl": CALLBACK_URL
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

    music_tasks[task_id] = {
        "status": "PENDING",
        "files": []
    }

    return {"success": True, "taskId": task_id}

# ======================
# CALLBACK (SUNO DOCS)
# ======================
@app.post("/music/callback")
async def music_callback(request: Request):
    payload = await request.json()

    # ACK cepat supaya tidak retry
    if payload.get("code") != 200:
        return {"ok": True}

    data = payload.get("data", {})
    callback_type = data.get("callbackType")
    task_id = data.get("task_id")

    if not task_id:
        return {"ok": True}

    # Hanya proses saat complete
    if callback_type != "complete":
        music_tasks.setdefault(task_id, {"status": "PROCESSING", "files": []})
        return {"ok": True}

    results: List[dict] = data.get("data", [])
    if not results:
        return {"ok": True}

    saved_files = []

    async with httpx.AsyncClient(timeout=60) as client:
        for i, item in enumerate(results):
            audio_url = item.get("audio_url")
            if not audio_url:
                continue

            filename = f"{task_id}_{i}.mp3"
            path = os.path.join(SAVE_DIR, filename)

            # Idempotent (callback retry aman)
            if os.path.exists(path):
                saved_files.append(filename)
                continue

            audio = await client.get(audio_url)
            if not audio.ok:
                continue

            with open(path, "wb") as f:
                f.write(audio.content)

            saved_files.append(filename)

    music_tasks[task_id] = {
        "status": "DONE",
        "files": saved_files
    }

    return {"ok": True}

# ======================
# STATUS
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
@app.get("/play/{task_id}/{index}")
def play(task_id: str, index: int):
    path = os.path.join(SAVE_DIR, f"{task_id}_{index}.mp3")
    if not os.path.exists(path):
        raise HTTPException(404, "Audio belum siap")

    return FileResponse(path, media_type="audio/mpeg")

# ======================
# DOWNLOAD
# ======================
@app.get("/download/{task_id}/{index}")
def download(task_id: str, index: int):
    path = os.path.join(SAVE_DIR, f"{task_id}_{index}.mp3")
    if not os.path.exists(path):
        raise HTTPException(404, "Audio belum siap")

    return FileResponse(path, filename=f"{task_id}_{index}.mp3")
