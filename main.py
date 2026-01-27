from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any
import requests
import os
import time
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="AI Music Generator (Suno API)")

SUNO_API_URL = os.getenv("SUNO_API_URL", "https://api.sunoapi.org/api/v1/generate")
SUNO_STATUS_URL = os.getenv("SUNO_STATUS_URL", "https://api.sunoapi.org/api/v1/status")
SUNO_TOKEN = os.getenv("SUNO_TOKEN")

BASE_URL = os.getenv("BASE_URL", "https://musik-android.onrender.com")
CALLBACK_URL = f"{BASE_URL}/callback"

if not SUNO_TOKEN:
    raise Exception("SUNO_TOKEN belum diisi di Render Environment Variables")

RESULTS: Dict[str, Any] = {}
TASKS: Dict[str, Any] = {}


class GenerateRequest(BaseModel):
    prompt: str
    style: str = "Pop"
    title: str = "My AI Song"
    instrumental: bool = False
    customMode: bool = True
    model: str = "V3_5"
    lyrics: Optional[str] = None
    negativeTags: Optional[str] = None


def extract_task_id(data: Any) -> Optional[str]:
    if not isinstance(data, dict):
        return None
    return (
        data.get("taskId")
        or (data.get("data") or {}).get("taskId")
        or data.get("id")
        or (data.get("data") or {}).get("id")
    )


def suno_status(task_id: str) -> Dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {SUNO_TOKEN}",
        "Accept": "application/json"
    }
    r = requests.get(SUNO_STATUS_URL, params={"taskId": task_id}, headers=headers, timeout=60)
    return {"status_code": r.status_code, "json": r.json()}


def is_done(status_json: Any) -> bool:
    """
    Karena format status bisa beda-beda, ini dibuat fleksibel.
    Kalau sudah ada url audio atau status done/success -> dianggap selesai.
    """
    if not isinstance(status_json, dict):
        return False

    text = str(status_json).lower()
    if "success" in text or "completed" in text or "done" in text:
        return True
    if "audio" in text and ("http" in text or "https" in text):
        return True
    return False


@app.get("/")
def home():
    return {
        "status": "ok",
        "callbackUrl_used": CALLBACK_URL,
        "endpoints": {
            "POST /generate": "Generate music + optional lyrics",
            "POST /callback": "Callback receiver",
            "GET /result/{taskId}": "Result callback by taskId",
            "GET /result-latest": "Last callback",
            "GET /music/status?taskId=...": "Check status to Suno",
            "GET /wait/{taskId}": "Wait until done (polling, no time limit in code)"
        }
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
        "callBackUrl": CALLBACK_URL
    }

    if body.negativeTags:
        payload["negativeTags"] = body.negativeTags

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

        if task_id:
            TASKS[task_id] = {
                "request": payload,
                "created_at": time.time(),
                "suno_response": data
            }

        return {
            "status": "sent",
            "taskId": task_id,
            "callbackUrl": CALLBACK_URL,
            "suno_status_code": r.status_code,
            "suno_response": data,
            "next_step": "Buka /wait/{taskId} atau /music/status?taskId=..."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/callback")
async def callback(request: Request):
    data = await request.json()
    task_id = extract_task_id(data)

    key = task_id if task_id else "latest"
    RESULTS[key] = data
    RESULTS["latest"] = data

    print("=== CALLBACK FROM SUNO ===")
    print(data)

    return {"status": "ok", "saved_as": key}


@app.get("/result/{task_id}")
def get_result(task_id: str):
    if task_id not in RESULTS:
        return {
            "status": "pending",
            "message": "Belum ada callback masuk untuk taskId ini.",
            "taskId": task_id
        }
    return RESULTS[task_id]


@app.get("/result-latest")
def get_latest_result():
    if "latest" not in RESULTS:
        return {"status": "pending", "message": "Belum ada callback masuk."}
    return RESULTS["latest"]


@app.get("/music/status")
def music_status(taskId: str):
    try:
        st = suno_status(taskId)
        return {"taskId": taskId, "suno": st}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/wait/{task_id}")
def wait_until_done(task_id: str):
    """
    Nunggu sampai selesai (tanpa batas waktu di code).
    Tapi kalau Render memutus koneksi karena timeout, kamu tinggal panggil lagi.
    """
    while True:
        # kalau callback sudah masuk, langsung return
        if task_id in RESULTS:
            return {"status": "done", "source": "callback", "data": RESULTS[task_id]}

        # kalau belum ada callback, polling status ke Suno
        try:
            st = suno_status(task_id)
            if is_done(st.get("json")):
                return {"status": "done", "source": "polling", "data": st}
        except Exception as e:
            # kalau status error, tetap lanjut polling
            print("polling error:", str(e))

        time.sleep(5)  # polling tiap 5 detik

