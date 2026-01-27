import os
import logging
import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# =====================================================
# CONFIG (pakai ENV atau default)
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
            "generate": "/generate",
            "callback": "/callback/suno"
        }
    }

# =====================================================
# GENERATE MUSIC (CLIENT HIT)
# =====================================================
@app.post("/generate")
async def generate_music(request: Request):
    body = await request.json()

    payload = {
        "customMode": True,
        "instrumental": body.get("instrumental", True),
        "model": body.get("model", "V4_5ALL"),
        "callBackUrl": CALLBACK_URL,
        "prompt": body.get("prompt"),
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

        return JSONResponse(
            content=response.json(),
            status_code=response.status_code
        )

    except Exception as e:
        logging.exception("Generate request failed")
        return JSONResponse(
            {"error": "generate_failed", "message": str(e)},
            status_code=500
        )

# =====================================================
# CALLBACK FROM SUNO
# =====================================================
@app.post("/callback/suno")
async def suno_callback(request: Request):
    try:
        payload = await request.json()

        code = payload.get("code")
        msg = payload.get("msg")
        data = payload.get("data") or {}

        task_id = data.get("task_id")
        callback_type = data.get("callbackType")
        music_list = data.get("data") or []

        logging.info("=== SUNO CALLBACK RECEIVED ===")
        logging.info({
            "task_id": task_id,
            "callbackType": callback_type,
            "code": code,
            "msg": msg
        })

        if code == 200 and callback_type == "complete":
            for music in music_list:
                logging.info({
                    "music_id": music.get("id"),
                    "title": music.get("title"),
                    "duration": music.get("duration"),
                    "audio_url": music.get("audio_url"),
                    "image_url": music.get("image_url")
                })

        elif code != 200:
            logging.error("Music generation failed")

        # WAJIB balas 200
        return JSONResponse({"status": "received"}, status_code=200)

    except Exception as e:
        logging.exception("Callback processing error")
        return JSONResponse({"status": "error_handled"}, status_code=200)


