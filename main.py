from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any
import requests
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="AI Music Generator (Suno API)")

# =========================
# ENV
# =========================
SUNO_API_URL = os.getenv("SUNO_API_URL", "https://api.sunoapi.org/api/v1/generate")
SUNO_STATUS_URL = os.getenv("SUNO_STATUS_URL", "https://api.sunoapi.org/api/v1/status")  # optional
SUNO_TOKEN = os.getenv("SUNO_TOKEN")

# Base URL APP INI (musik-android)
BASE_URL = os.getenv("BASE_URL", "https://musik-android.onrender.com")
CALLBACK_URL = f"{BASE_URL}/callback"

if not SUNO_TOKEN:
    raise Exception("SUNO_TOKEN belum diisi. Set di Render -> Environment Variables")


# =========================
# In-memory storage
# =========================
RESULTS: Dict[str, Any] = {}


# =========================
# Request Model
# =========================
class GenerateRequest(BaseModel):
    prompt: str
    style: str = "True"
    title: str = "False"

    # Kalau instrumental=True, biasanya lyrics diabaikan
    instrumental: bool = False

    # customMode True biasanya untuk detail lebih
    customMode: bool = False

    # model harus sesuai API, biasanya "V3_5"
    model: str = "V3_5"

    # lirik (opsional)
    lyrics: Optional[str] = None

    # negative tags (opsional)
    negativeTags: Optional[str] = None


# =========================
# Helpers
# =========================
def extract_task_id(data: Any) -> Optional[str]:
    if not isinstance(data, dict):
        return None
    return (
        data.get("taskId")
        or (data.get("data") or {}).get("taskId")
        or data.get("id")
        or (data.get("data") or {}).get("id")
    )


# =========================
# Routes
# =========================
@app.get("/")
def home():
    return {
        "status": "ok",
        "service": "AI Music Generator (Suno API)",
        "endpoints": {
            "POST /generate": "Generate music (with optional lyrics)",
            "POST /callback": "Callback receiver from Suno",
            "GET /result-latest": "Get last callback payload",
            "GET /result/{taskId}": "Get callback payload by taskId",
            "GET /music/status?taskId=...": "Polling status (optional, depends on Suno API)"
        },
        "callbackUrl_used": CALLBACK_URL
    }


@app.post("/generate")
def generate_music(body: GenerateRequest):
    # payload ke Suno
    payload = {
        "prompt": body.prompt,
        "style": body.style,
        "title": body.title,
        "customMode": body.customMode,
        "instrumental": body.instrumental,
        "model": body.model,
        "callBackUrl": CALLBACK_URL
    }

    # kalau user isi negativeTags
    if body.negativeTags:
        payload["negativeTags"] = body.negativeTags

    # kalau user isi lyrics dan bukan instrumental
    if body.lyrics and not body.instrumental:
        payload["lyrics"] = body.lyrics

    headers = {
        "Authorization": f"Bearer {SUNO_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    try:
        r = requests.post(SUNO_API_URL, json=payload, headers=headers, timeout=60)
        data = r.json()
        task_id = extract_task_id(data)

        return {
            "status": "sent",
            "taskId": task_id,
            "callbackUrl": CALLBACK_URL,
            "suno_status_code": r.status_code,
            "suno_response": data,
            "next_step": "Tunggu 10-60 detik lalu cek GET /result/{taskId} atau GET /result-latest"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/callback")
async def callback(request: Request):
    data = await request.json()

    task_id = extract_task_id(data)
    key = task_id if task_id else "latest"

    RESULTS[key] = data
    RESULTS["latest"] = data  # selalu simpan yang terakhir juga

    print("=== CALLBACK FROM SUNO ===")
    print(data)

    return {"status": "ok", "saved_as": key}


@app.get("/result/{task_id}")
def get_result(task_id: str):
    if task_id not in RESULTS:
        return {
            "status": "pending",
            "message": "Belum ada callback masuk untuk taskId ini. Tunggu sebentar lalu coba lagi.",
            "taskId": task_id
        }
    return RESULTS[task_id]


@app.get("/result-latest")
def get_latest_result():
    if "latest" not in RESULTS:
        return {
            "status": "pending",
            "message": "Belum ada callback masuk ke /callback. Tunggu sebentar lalu coba lagi."
        }
    return RESULTS["latest"]


# OPTIONAL: polling status langsung ke Suno (kalau endpoint status tersedia)
@app.get("/music/status")
def music_status(taskId: str):
    headers = {
        "Authorization": f"Bearer {SUNO_TOKEN}",
        "Accept": "application/json"
    }

    # Banyak API status bentuknya beda-beda.
    # Ini contoh umum: /status?taskId=xxxx
    try:
        r = requests.get(SUNO_STATUS_URL, params={"taskId": taskId}, headers=headers, timeout=60)
        return {
            "taskId": taskId,
            "suno_status_code": r.status_code,
            "suno_response": r.json()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




