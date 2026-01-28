from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import httpx
import os
from typing import Dict, Optional

# ======================
# CONFIG
# ======================
SUNO_URL_GENERATE = "https://api.sunoapi.org/api/v1/generate"
CALLBACK_URL = "https://musik-android.onrender.com/music/callback"

SUNO_TOKEN = os.getenv("SUNO_TOKEN")
if not SUNO_TOKEN:
    raise RuntimeError("SUNO_TOKEN belum diset di Render")

# ======================
# APP
# ======================
app = FastAPI(title="Music Generator API")

# task_id -> metadata
music_tasks: Dict[str, dict] = {}

# ======================
# MODELS
# ======================
class GenerateRequest(BaseModel):
    prompt: str
    style: Optional[str] = None
    title: Optional[str] = None
    vocal_gender: Optional[str] = Field(default=None, alias="vocalGender")

    class Config:
        populate_by_name = True

# ======================
# HEADERS
# ======================
def get_headers():
    return {
        "Authorization": f"Bearer {SUNO_TOKEN}",
        "Accept": "application/json",
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
    # ⛔ JANGAN kirim field None ke Suno
    payload = {
        "prompt": body.prompt,
        "model": "chirp-v3-5",
        "callbackUrl": CALLBACK_URL,
    }

    if body.style:
        payload["style"] = body.style
    if body.title:
        payload["title"] = body.title
    if body.vocal_gender:
        payload["vocalGender"] = body.vocal_gender

    try:
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(
                API_URL_GENERATE,
                json=payload,
                headers=get_headers(),
            )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Koneksi ke Suno gagal: {str(e)}",
        )

    # Log mentah (penting saat debug)
    if resp.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"Suno error {resp.status_code}: {resp.text}",
        )

    try:
        data = resp.json()
    except Exception:
        raise HTTPException(
            status_code=502,
            detail=f"Suno balas non-JSON: {resp.text}",
        )

    task_id = (
        data.get("taskId")
        or data.get("data", {}).get("taskId")
        or data.get("data", {}).get("task_id")
    )

    if not task_id:
        raise HTTPException(
            status_code=502,
            detail=f"Tidak ada taskId dari Suno: {data}",
        )

    # Simpan task
    music_tasks[task_id] = {
        "status": "pending",
        "prompt": body.prompt,
        "title": body.title,
    }

    return {
        "status": "queued",
        "taskId": task_id,
    }
