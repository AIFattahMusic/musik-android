import os
import logging
import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# =====================================================
# CONFIG
# =====================================================
SUNO_API_TOKEN = os.getenv("SUNO_API_TOKEN", "ISI_TOKEN_KAMU")
CALLBACK_URL = os.getenv(
    "CALLBACK_URL",
    "https://musik-android.onrender.com/callback/suno"
)
SUNO_GENERATE_URL = "https://api.sunoapi.org/api/v1/generate"

APP_NAME = os.getenv("APP_NAME", "Suno Music Service")
ENV = os.getenv("ENV", "production")

# =====================================================
# IN-MEMORY STORE (STATUS TASK)
# NOTE: akan hilang jika Render restart
# =====================================================
TASK_STORE = {}
# {
#   task_id: {
#       "status": "pending|complete|error",
#       "result": [...]
#   }
# }

# =====================================================
# LOGGING
# =====================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

# =====================================================
# FASTAPI APP
# =====================================================
app = FastAPI(
    title=APP_NAME,
    version="1.0.0"
)

# =====================================================
# ROOT / HEALTH CHECK
# =====================================================
@app.get("/")
def root():
    return {
        "status": "ok",
        "service": APP_NAME,
        "env": ENV,
        "endpoints": {
            "generate": "POST /generate",
            "status": "GET /status/{task_id}",
            "callback": "POST /callback/suno"
        }
    }

# =====================================================
# GENERATE MUSIC (CLIENT HIT INI)
# =====================================================
@app.post("/generate")
async def generate_music(request: Request):
    # ---- aman walau body kosong / invalid
    try:
        body = await request.json()
    except:
        return JSONResponse(
            {
                "error": "invalid_json",
                "message": "Request body must be valid JSON"
            },
            status_code=400
        )

    # ---- validasi wajib
    prompt = body.get("prompt")
    if not prompt:
        return JSONResponse(
            {
                "error": "missing_prompt",
                "message": "Field 'prompt' is required"
            },
            status_code=400
        )

    # ---- payload ke Suno
    payload = {
        "customMode": True,
        "instrumental": body.get("instrumental", True),
        "model": body.get("model", "V4_5ALL"),
        "callBackUrl": CALLBACK_URL,
        "prompt": prompt,
        "style": body.get("style", "Classical"),
        "title": body.get("title", "Generated Music"),
        "personaId": body.get("personaId"),
        "negativeTags": body.get("negativeTags"),
        "vocalGender": body.get("vocalGender", "m"),
        "styleWeight": body.get("styleWeight", 0.65),
        "weirdnessConstraint": body.get("weirdnessConstraint", 0.65),
        "audioWeight": body.get("audioWeight", 0.65)
    }

    headers = {
        "Authorization": f"Bearer {SUNO_API_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(
            SUNO_GENERATE_URL,
            json=payload,
            headers=headers,
            timeout=30
        )

        data = response.json()

        # ---- simpan task_id untuk cek status
        task_id = data.get("data", {}).get("taskId")
        if task_id:
            TASK_STORE[task_id] = {
                "status": "pending",
                "result": None
            }

        return JSONResponse(
            content=data,
            status_code=response.status_code
        )

    except Exception as e:
        logging.exception("Generate request failed")
        return JSONResponse(
            {
                "error": "suno_request_failed",
                "message": str(e)
            },
            status_code=500
        )

# =====================================================
# CALLBACK DARI SUNO (JANGAN DIPANGGIL MANUAL)
# =====================================================
@app.post("/callback/suno")
async def suno_callback(request: Request):
    try:
        payload = await request.json()

        code = payload.get("code")
        data = payload.get("data") or {}

        task_id = data.get("task_id")
        callback_type = data.get("callbackType")
        music_list = data.get("data")

        logging.info("SUNO CALLBACK RECEIVED")
        logging.info({
            "task_id": task_id,
            "callbackType": callback_type,
            "code": code
        })

        if not task_id:
            return JSONResponse({"status": "ignored"}, status_code=200)

        if code == 200 and callback_type == "complete":
            TASK_STORE[task_id] = {
                "status": "complete",
                "result": music_list
            }
        else:
            TASK_STORE[task_id] = {
                "status": "error",
                "result": None
            }

        return JSONResponse({"status": "received"}, status_code=200)

    except Exception:
        logging.exception("Callback error")
        return JSONResponse({"status": "error_handled"}, status_code=200)

# =====================================================
# CEK STATUS (CLIENT POLLING)
# =====================================================
@app.get("/status/{task_id}")
def check_status(task_id: str):
    task = TASK_STORE.get(task_id)

    if not task:
        return JSONResponse(
            {"status": "not_found"},
            status_code=404
        )

    return {
        "task_id": task_id,
        "status": task["status"],
        "result": task["result"]
    }

