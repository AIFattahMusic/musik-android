import os
import time
import requests
from typing import Optional, Dict, Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


app = FastAPI(title="Generator Musik AI (API Suno)", version="0.1.0")

# =========================
# CORS (biar Android aman)
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# ENV
# =========================
SUNO_API_URL = os.getenv("SUNO_API_URL", "https://api.sunoapi.org/api/v1/generate")
SUNO_TOKEN = os.getenv("SUNO_TOKEN")

# Base URL backend kamu (Render)
BASE_URL = os.getenv("BASE_URL", "https://musik-android.onrender.com")
CALLBACK_URL = f"{BASE_URL}/panggilan_balik"

if not SUNO_TOKEN:
    raise Exception("SUNO_TOKEN belum diisi. Set di Render -> Environment Variables")

# =========================
# In-memory storage
# =========================
RESULTS: Dict[str, Any] = {}  # simpan callback berdasarkan taskId
LATEST_TASK_ID: Optional[str] = None


# =========================
# Request Model
# =========================
class HasilkanPermintaan(BaseModel):
    prompt: str
    style: Optional[str] = ""
    title: Optional[str] = ""
    customMode: bool = False
    instrumental: bool = False
    model: str = "V4_5"
    negativeTags: Optional[str] = ""


# =========================
# Helper
# =========================
def extract_task_id(resp: Any) -> Optional[str]:
    """
    SunoApi.org biasanya balikin:
    { code:200, data:{ task_id:"..." } }
    atau variasi lain.
    """
    if not isinstance(resp, dict):
        return None

    # format umum
    if "data" in resp and isinstance(resp["data"], dict):
        if "task_id" in resp["data"]:
            return resp["data"]["task_id"]
        if "taskId" in resp["data"]:
            return resp["data"]["taskId"]

    # fallback
    return resp.get("task_id") or resp.get("taskId") or resp.get("id")


def pick_audio_url_from_callback(callback_payload: dict) -> Optional[str]:
    """
    Callback complete biasanya punya:
    payload["data"]["data"] = [ { audio_url: "....mp3" }, ... ]
    """
    try:
        data = callback_payload.get("data", {})
        tracks = data.get("data", [])
        if isinstance(tracks, list) and len(tracks) > 0:
            first = tracks[0]
            # prioritas mp3 url
            return first.get("audio_url") or first.get("source_audio_url")
    except:
        return None
    return None


# =========================
# ROUTES
# =========================
@app.get("/")
def home():
    return {
        "status": "ok",
        "service": "Generator Musik AI (API SunoApi.org)",
        "base_url": BASE_URL,
        "callback_url_used": CALLBACK_URL,
        "endpoints": {
            "POST /menghasilkan": "Mulai generate musik",
            "POST /panggilan_balik": "Callback dari SunoApi.org",
            "GET /hasil/{id_tugas}": "Ambil payload callback berdasarkan taskId",
            "GET /hasil-terbaru": "Ambil payload callback terbaru",
            "GET /musik/status?taskId=...": "Status generate + audio_url (kalau sudah ada)",
        },
    }


# ==========================================
# 1) GENERATE (Android panggil ini)
# ==========================================
@app.post("/menghasilkan")
def menghasilkan(body: HasilkanPermintaan):
    global LATEST_TASK_ID

    payload = {
        "prompt": body.prompt,
        "customMode": body.customMode,
        "instrumental": body.instrumental,
        "model": body.model,
        "callBackUrl": CALLBACK_URL,
    }

    # aturan SunoApi.org:
    # - kalau customMode=true -> style & title wajib
    if body.customMode:
        payload["style"] = body.style
        payload["title"] = body.title

        if body.negativeTags:
            payload["negativeTags"] = body.negativeTags

    # header wajib
    headers = {
        "Authorization": f"Bearer {SUNO_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        r = requests.post(SUNO_API_URL, json=payload, headers=headers, timeout=60)
        data = r.json()
    except Exception as e:
        return {"status": "error", "message": f"Request gagal: {str(e)}"}

    task_id = extract_task_id(data)
    if task_id:
        LATEST_TASK_ID = task_id

    return {
        "status": "sent",
        "taskId": task_id,
        "callbackUrl": CALLBACK_URL,
        "suno_status_code": r.status_code,
        "suno_response": data,
        "next_step": "Panggil GET /musik/status?taskId=... setiap 3-5 detik sampai audio_url muncul",
    }


# ==========================================
# 2) CALLBACK (SunoApi.org akan POST ke sini)
# ==========================================
@app.post("/panggilan_balik")
async def panggilan_balik(request: Request):
    global LATEST_TASK_ID

    payload = await request.json()

    # ambil task_id dari callback
    task_id = None
    try:
        task_id = payload.get("data", {}).get("task_id")
    except:
        task_id = None

    if not task_id:
        # simpan sebagai latest kalau taskId tidak ada
        RESULTS["latest"] = payload
        return {"status": "ok", "saved_as": "latest"}

    RESULTS[task_id] = payload
    RESULTS["latest"] = payload
    LATEST_TASK_ID = task_id

    # ambil audio_url jika complete
    audio_url = pick_audio_url_from_callback(payload)

    return {
        "status": "ok",
        "taskId": task_id,
        "callbackType": payload.get("data", {}).get("callbackType"),
        "audio_url": audio_url,
    }


# ==========================================
# 3) GET hasil callback berdasarkan taskId
# ==========================================
@app.get("/hasil/{id_tugas}")
def hasil(id_tugas: str):
    if id_tugas not in RESULTS:
        return {
            "status": "pending",
            "message": "Belum ada callback masuk untuk taskId ini. Tunggu lalu cek lagi.",
            "taskId": id_tugas,
        }
    return RESULTS[id_tugas]


@app.get("/hasil-terbaru")
def hasil_terbaru():
    if "latest" not in RESULTS:
        return {"status": "pending", "message": "Belum ada callback masuk."}
    return RESULTS["latest"]


# ==========================================
# 4) STATUS untuk Android (ini yang dipakai)
# ==========================================
@app.get("/musik/status")
def musik_status(taskId: str):
    """
    Android cukup panggil ini berulang.
    Kalau callback sudah masuk dan complete -> audio_url muncul.
    """
    if taskId not in RESULTS:
        return {
            "status": "pending",
            "taskId": taskId,
            "message": "Masih menunggu callback dari SunoApi.org...",
            "audio_url": None,
        }

    payload = RESULTS[taskId]
    callback_type = payload.get("data", {}).get("callbackType")
    audio_url = pick_audio_url_from_callback(payload)

    if callback_type == "complete" and audio_url:
        return {
            "status": "complete",
            "taskId": taskId,
            "audio_url": audio_url,  # ini mp3 direct
            "payload": payload,
        }

    return {
        "status": "processing",
        "taskId": taskId,
        "callbackType": callback_type,
        "audio_url": audio_url,
        "message": "Callback sudah masuk tapi belum complete. Tunggu sebentar...",
    }
