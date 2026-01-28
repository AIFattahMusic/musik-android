from fastapi import FastAPI, HTTPException, Request
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
if not SUNO_TOKEN:
    raise RuntimeError("SUNO_TOKEN belum diset di Render")

# ======================
# APP
# ======================
app = FastAPI(title="Music Generator API")

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
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

# ======================
# ROOT
# ======================
@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "music-generator",
    }

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
        "model": "chirp-v3-5",
        "callbackUrl": CALLBACK_URL,
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                API_URL_GENERATE,
                json=payload,
                headers=get_headers(),
            )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal koneksi ke Suno API: {str(e)}",
        )

    if resp.status_code >= 400:
        raise HTTPException(
            status_code=resp.status_code,
            detail=resp.text,
        )

    try:
        data = resp.json()
    except Exception:
        raise HTTPException(
            status_code=500,
            detail=f"Response Suno bukan JSON: {resp.text}",
        )

    task_id = (
        data.get("taskId")
        or data.get("data", {}).get("taskId")
        or data.get("data", {}).get("task_id")
    )

    if not task_id:
        raise HTTPException(
            status_code=500,
            detail=f"Response Suno tidak valid: {data}",
        )

    music_tasks[task_id] = {
        "status": "PENDING",
        "files": [],
    }

    return {
        "success": True,
        "taskId": task_id,
    }

# ======================
# CHECK STATUS
# ======================
@app.get("/music/status/{task_id}")
def music_status(task_id: str):
    task = music_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task tidak ditemukan")

    return {
        "taskId": task_id,
        "status": task["status"],
        "files": task.get("files", []),
        "error": task.get("error"),
    }

# ======================
# CALLBACK (SUNO)
# ======================
@app.post("/music/callback")
async def music_callback(request: Request):
    try:
        payload = await request.json()
    except Exception:
        return {"ok": True}

    # ACK cepat supaya Suno tidak retry
    if payload.get("code") != 200:
        return {"ok": True}

    data = payload.get("data", {})
    callback_type = data.get("callbackType")
    task_id = data.get("task_id")

    if not task_id:
        return {"ok": True}

    # Pastikan task ada
    task = music_tasks.setdefault(
        task_id,
        {"status": "UNKNOWN", "files": []},
    )

    if callback_type == "progress":
        task["status"] = "PROCESSING"

    elif callback_type == "complete":
        task["status"] = "DONE"
        task["files"] = data.get("audioUrls", [])

    elif callback_type == "error":
        task["status"] = "ERROR"
        task["error"] = data.get("message")

    return {"ok": True}
