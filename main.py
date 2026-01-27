from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import requests
import os
import json
import re
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Suno Generator + Callback Render")

SUNO_API_URL = os.getenv("SUNO_API_URL", "https://api.sunoapi.org/api/v1/generate")
SUNO_TOKEN = os.getenv("SUNO_TOKEN")

# Callback kamu (Render)
CALLBACK_URL = "https://ai-music-fattah.onrender.com/callback"

if not SUNO_TOKEN:
    raise Exception("SUNO_TOKEN belum diisi. Isi di file .env: SUNO_TOKEN=token_kamu")

# Simpan hasil callback di memory
RESULTS = {}  # key: taskId / id / "latest"


# =========================
# Request body
# =========================
class GenerateRequest(BaseModel):
    prompt: str
    style: str = "Classical"
    title: str = "False"
    customMode: bool = False
    instrumental: bool = False
    model: str = "V3_5"
    negativeTags: str = "False"


# =========================
# Helpers
# =========================
def extract_urls(text: str):
    if not isinstance(text, str):
        return []
    return re.findall(r"https?://[^\s\"\'\)\]]+", text)


def find_audio_urls(obj):
    found = []

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                key = str(k).lower()

                if isinstance(v, str):
                    if v.startswith("http"):
                        if (
                            "audio" in key
                            or "url" in key
                            or "link" in key
                            or v.lower().endswith((".mp3", ".wav", ".m4a"))
                        ):
                            found.append(v)

                    for u in extract_urls(v):
                        if u.lower().endswith((".mp3", ".wav", ".m4a")) or "audio" in u.lower():
                            found.append(u)

                walk(v)

        elif isinstance(x, list):
            for item in x:
                walk(item)

        elif isinstance(x, str):
            for u in extract_urls(x):
                if u.lower().endswith((".mp3", ".wav", ".m4a")) or "audio" in u.lower():
                    found.append(u)

    walk(obj)
    return list(dict.fromkeys(found))


def guess_task_id(obj):
    if not isinstance(obj, dict):
        return None
    data_obj = obj.get("data") or {}
    return (
        obj.get("taskId")
        or obj.get("id")
        or data_obj.get("taskId")
        or data_obj.get("id")
    )


def guess_status(obj):
    if not isinstance(obj, dict):
        return None
    data_obj = obj.get("data") or {}
    return (
        obj.get("status")
        or data_obj.get("status")
        or obj.get("state")
        or data_obj.get("state")
    )


# =========================
# Routes
# =========================
@app.get("/")
def home():
    return {
        "status": "ok",
        "generate": "/generate",
        "callback": "/callback",
        "check_status": "/music/status",
        "callback_url_used": CALLBACK_URL
    }


@app.post("/generate")
def generate_music(body: GenerateRequest):
    payload = {
        "prompt": body.prompt,
        "style": body.style,
        "title": body.title,
        "customMode": body.customMode,
        "instrumental": body.instrumental,
        "model": body.model,
        "negativeTags": body.negativeTags,
        "callBackUrl": CALLBACK_URL
    }

    headers = {
        "Authorization": f"Bearer {SUNO_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    try:
        r = requests.post(SUNO_API_URL, json=payload, headers=headers, timeout=60)
        resp = r.json()
        task_id = guess_task_id(resp)

        return {
            "status": "sent",
            "taskId": task_id,
            "callbackUrl": CALLBACK_URL,
            "suno_status_code": r.status_code,
            "suno_response": resp,
            "next_step": "Tunggu 10-60 detik lalu cek GET /music/status"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/callback")
async def callback(request: Request):
    """
    Suno akan POST hasil ke sini
    """
    data = await request.json()

    task_id = guess_task_id(data)
    key = task_id if task_id else "latest"

    RESULTS[key] = data
    RESULTS["latest"] = data

    print("=== CALLBACK FROM SUNO ===")
    print(json.dumps(data, indent=2))

    return {"status": "ok", "saved_as": key}


@app.get("/music/status")
def music_status():
    """
    Cek status:
    - pending kalau belum ada audio_url
    - done kalau sudah ada audio_url
    """
    latest = RESULTS.get("latest")

    if not latest:
        return {
            "status": "pending",
            "message": "Belum ada callback masuk ke /callback. Pastikan app Render kamu ON dan URL callback benar."
        }

    audio_urls = find_audio_urls(latest)
    status_guess = guess_status(latest)
    task_id = guess_task_id(latest)

    if audio_urls:
        return {
            "status": "done",
            "taskId": task_id,
            "audio_url": audio_urls[0],
            "all_audio_urls": audio_urls,
            "status_guess": status_guess
        }

    return {
        "status": "pending",
        "taskId": task_id,
        "status_guess": status_guess,
        "message": "Callback sudah masuk, tapi audio_url belum ada (masih proses). Coba lagi 10-30 detik."
    }

