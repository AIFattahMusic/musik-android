from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import Optional, Any, Dict
import os
import time
import requests

app = FastAPI()

SUNO_TOKEN = os.getenv("SUNO_TOKEN")
SUNO_GENERATE_URL = "https://api.sunoapi.org/api/v1/generate"
SUNO_STATUS_URL = "https://api.sunoapi.org/api/v1/generate/status"  # pakai query taskId

BASE_URL = os.getenv("BASE_URL", "https://musik-android.onrender.com")
CALLBACK_URL = f"{BASE_URL}/callback"

if not SUNO_TOKEN:
    raise Exception("SUNO_TOKEN belum di set di Render Environment Variables")

# simpan hasil callback
RESULTS: Dict[str, Any] = {}

class GenerateRequest(BaseModel):
    prompt: str
    style: Optional[str] = None
    title: Optional[str] = None
    customMode: bool = False
    instrumental: bool = False
    model: str = "V4_5"
    negativeTags: Optional[str] = None


def headers():
    return {
        "Authorization": f"Bearer {SUNO_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def extract_task_id(resp: dict) -> Optional[str]:
    return (
        resp.get("taskId")
        or resp.get("task_id")
        or (resp.get("data") or {}).get("taskId")
        or (resp.get("data") or {}).get("task_id")
    )


def normalize_music(payload: dict, task_id: str):
    """
    Ambil audio_url(mp3) dan stream_audio_url dari response Suno callback/status
    """
    mp3 = None
    stream = None
    image = None
    title = None
    lyrics = None

    data = payload.get("data")

    # callback format: data: { callbackType, task_id, data: [ {audio_url, stream_audio_url,...} ] }
    if isinstance(data, dict):
        inner = data.get("data")
        if isinstance(inner, list) and len(inner) > 0:
            item = inner[0]
            mp3 = item.get("audio_url")
            stream = item.get("stream_audio_url")
            image = item.get("image_url")
            title = item.get("title")
            lyrics = item.get("prompt")

    # status format bisa beda, jadi cari juga kalau langsung list
    if isinstance(data, list) and len(data) > 0:
        item = data[0]
        mp3 = item.get("audio_url") or mp3
        stream = item.get("stream_audio_url") or stream
        image = item.get("image_url") or image
        title = item.get("title") or title
        lyrics = item.get("prompt") or lyrics

    return {
        "status": "done" if mp3 or stream else "pending",
        "taskId": task_id,
        "mp3": mp3,          # ✅ MP3 direct
        "image": image,
        "title": title,
        "lyrics": lyrics,
    }


@app.get("/")
def root():
    return {"status": "ok"}


@app.post("/generate")
def generate(body: GenerateRequest):
    payload = {
        "prompt": body.prompt,
        "customMode": body.customMode,
        "instrumental": body.instrumental,
        "model": body.model,
        "callBackUrl": CALLBACK_URL,
    }

    if body.customMode:
        payload["style"] = body.style
        payload["title"] = body.title

    if body.negativeTags:
        payload["negativeTags"] = body.negativeTags

    r = requests.post(SUNO_GENERATE_URL, json=payload, headers=headers(), timeout=60)
    data = r.json()
    task_id = extract_task_id(data)

    return {
        "status": "sent",
        "taskId": task_id,
        "callbackUrl": CALLBACK_URL,
        "suno": data
    }


@app.post("/callback")
async def callback(req: Request):
    data = await req.json()

    task_id = None
    if isinstance(data, dict):
        task_id = (data.get("data") or {}).get("task_id") or data.get("task_id")

    if task_id:
        RESULTS[task_id] = data
        RESULTS["latest"] = data

    return {"status": "ok", "taskId": task_id}


@app.get("/result/{task_id}")
def result(task_id: str):
    if task_id not in RESULTS:
        return {"status": "pending", "taskId": task_id, "message": "Belum ada callback masuk"}
    return normalize_music(RESULTS[task_id], task_id)


@app.get("/music/status")
def music_status(taskId: str):
    """
    Polling status dari Suno (tanpa callback juga bisa)
    """
    r = requests.get(
        SUNO_STATUS_URL,
        params={"taskId": taskId},
        headers=headers(),
        timeout=240
    )
    payload = r.json()

    # simpan juga biar bisa dipanggil /result/{taskId}
    RESULTS[taskId] = payload
    RESULTS["latest"] = payload

    return normalize_music(payload, taskId)


@app.get("/music/wait")
def music_wait(taskId: str, delay: int = 3):
    """
    Tunggu sampai MP3/stream muncul (biar Android gampang)
    """
    while True:
        r = requests.get(
            SUNO_STATUS_URL,
            params={"taskId": taskId},
            headers=headers(),
            timeout=240
        )
        payload = r.json()

        out = normalize_music(payload, taskId)
        if out["mp3"] or out["stream"]:
            RESULTS[taskId] = payload
            RESULTS["latest"] = payload
            return out

        time.sleep(delay)
