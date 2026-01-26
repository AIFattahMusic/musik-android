from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import Optional, Any, Dict
import os
import time
import requests

app = FastAPI(title="Generator Musik AI (SunoAPI)")

# =========================
# ENV
# =========================
SUNO_API_URL = os.getenv("SUNO_API_URL", "https://api.sunoapi.org/api/v1/generate")
SUNO_TOKEN = os.getenv("SUNO_TOKEN")

# STATUS ENDPOINT YANG BENAR (DETAIL TASK)
SUNO_STATUS_TEMPLATE = os.getenv(
    "SUNO_STATUS_TEMPLATE",
    "https://api.sunoapi.org/api/v1/generate/{taskId}"
)

# BASE URL BACKEND KAMU (Render)
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
    style: Optional[str] = None
    title: Optional[str] = None

    customMode: bool = False
    instrumental: bool = False
    model: str = "V4_5"

    negativeTags: Optional[str] = None

    # kalau mau lirik custom (opsional)
    lyrics: Optional[str] = None


# =========================
# Helpers
# =========================
def extract_task_id(data: Any) -> Optional[str]:
    if not isinstance(data, dict):
        return None
    return (
        data.get("taskId")
        or data.get("task_id")
        or (data.get("data") or {}).get("taskId")
        or (data.get("data") or {}).get("task_id")
    )


def suno_headers():
    return {
        "Authorization": f"Bearer {SUNO_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def get_suno_status(task_id: str) -> dict:
    url = SUNO_STATUS_TEMPLATE.format(taskId=task_id)
    r = requests.get(url, headers=suno_headers(), timeout=60)
    return {"status_code": r.status_code, "json": r.json()}


def find_audio_url(payload: Any) -> Optional[str]:
    """
    Cari audio_url dari response Suno (bisa beda struktur)
    """
    if not isinstance(payload, dict):
        return None

    data = payload.get("data")

    # kadang data itu list
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and item.get("audio_url"):
                return item.get("audio_url")

    # kadang data itu dict punya "data": [...]
    if isinstance(data, dict):
        inner = data.get("data")
        if isinstance(inner, list):
            for item in inner:
                if isinstance(item, dict) and item.get("audio_url"):
                    return item.get("audio_url")

        # kadang langsung ada audio_url
        if data.get("audio_url"):
            return data.get("audio_url")

    return None


# =========================
# Routes
# =========================
@app.get("/")
def home():
    return {
        "status": "ok",
        "service": "AI Music Generator (SunoAPI)",
        "endpoints": {
            "POST /generate": "Generate music (with lyrics optional)",
            "POST /callback": "Callback receiver from Suno",
            "GET /result/{task_id}": "Get callback saved by task_id",
            "GET /result-latest": "Get latest callback saved",
            "GET /music/status?taskId=...": "Polling status from Suno (returns audio_url if ready)",
            "GET /music/wait?taskId=...": "WAIT until audio_url ready (no limit)",
        },
        "callbackUrl_used": CALLBACK_URL
    }


@app.post("/generate")
def generate_music(body: GenerateRequest):
    payload = {
        "customMode": body.customMode,
        "instrumental": body.instrumental,
        "model": body.model,
        "callBackUrl": CALLBACK_URL,
    }

    # Mode NON-custom: cuma prompt
    if body.customMode is False:
        payload["prompt"] = body.prompt

    # Mode custom: butuh style & title
    else:
        if not body.style or not body.title:
            return {
                "status": "error",
                "message": "customMode=true wajib isi style dan title"
            }

        payload["style"] = body.style
        payload["title"] = body.title

        # kalau instrumental false -> prompt dipakai sebagai lirik
        if body.instrumental is False:
            # kalau user isi lyrics, pakai itu
            if body.lyrics:
                payload["prompt"] = body.lyrics
            else:
                payload["prompt"] = body.prompt

    if body.negativeTags:
        payload["negativeTags"] = body.negativeTags

    try:
        r = requests.post(SUNO_API_URL, json=payload, headers=suno_headers(), timeout=60)
        data = r.json()
        task_id = extract_task_id(data)

        return {
            "status": "sent",
            "taskId": task_id,
            "callbackUrl": CALLBACK_URL,
            "suno_status_code": r.status_code,
            "suno_response": data,
            "next_step": f"Cek status: GET /music/status?taskId={task_id}"
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/callback")
async def callback_receiver(req: Request):
    data = await req.json()

    task_id = None
    if isinstance(data, dict):
        task_id = (data.get("data") or {}).get("task_id") or data.get("task_id")

    key = task_id if task_id else "latest"

    RESULTS[key] = data
    RESULTS["latest"] = data

    print("=== CALLBACK FROM SUNO ===")
    print(data)

    return {"status": "ok", "saved_as": key}


@app.get("/result/{task_id}")
def get_result(task_id: str):
    if task_id not in RESULTS:
        return {"status": "pending", "message": "Belum ada callback masuk", "taskId": task_id}
    return RESULTS[task_id]


@app.get("/result-latest")
def get_latest_result():
    if "latest" not in RESULTS:
        return {"status": "pending", "message": "Belum ada callback masuk"}
    return RESULTS["latest"]


@app.get("/music/status")
def music_status(taskId: str):
    """
    Polling sekali (1x cek) ke Suno detail task
    """
    try:
        res = get_suno_status(taskId)
        payload = res["json"]
        audio_url = find_audio_url(payload)

        return {
            "taskId": taskId,
            "suno_status_code": res["status_code"],
            "audio_url": audio_url,
            "suno_response": payload
        }

    except Exception as e:
        return {"taskId": taskId, "status": "error", "message": str(e)}


@app.get("/music/wait")
def music_wait(taskId: str, delay: int = 3):
    """
    NUNGGU TERUS sampai audio_url muncul (NO LIMIT)
    delay default 3 detik biar gak spam server
    """
    while True:
        try:
            res = get_suno_status(taskId)
            payload = res["json"]
            audio_url = find_audio_url(payload)

            if audio_url:
                return {
                    "taskId": taskId,
                    "status": "done",
                    "audio_url": audio_url,
                    "suno_status_code": res["status_code"],
                    "suno_response": payload
                }

        except Exception as e:
            return {"taskId": taskId, "status": "error", "message": str(e)}

        time.sleep(delay)
