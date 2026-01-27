import os
import logging
import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# =====================================================
# CONFIG
# =====================================================
SUNO_API_TOKEN = os.getenv("SUNO_API_TOKEN", "")
SUNO_BASE_URL = "https://api.sunoapi.org"

APP_NAME = "Suno Music API"

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
app = FastAPI(title=APP_NAME, version="1.0.0")

# =====================================================
# ROOT (CEK SERVER)
# =====================================================
@app.get("/")
def root():
    return {
        "status": "ok",
        "service": APP_NAME,
        "endpoints": {
            "generate": "POST /generate",
            "status": "GET /status/{task_id}"
        }
    }

# =====================================================
# GENERATE LAGU (INI YANG BIKIN LAGU)
# =====================================================
@app.post("/generate")
async def generate_music(request: Request):
    try:
        body = await request.json()
    except:
        return JSONResponse(
            {"error": "invalid_json"},
            status_code=400
        )

    prompt = body.get("prompt")
    if not prompt:
        return JSONResponse(
            {"error": "prompt_required"},
            status_code=400
        )

    payload = {
        "customMode": True,
        "instrumental": body.get("instrumental", False),
        "model": body.get("model", "V4_5ALL"),
        "prompt": prompt,
        "style": body.get("style", "Pop"),
        "title": body.get("title", "Generated Song"),
        "vocalGender": body.get("vocalGender", "f")
    }

    headers = {
        "Authorization": f"Bearer {SUNO_API_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        r = requests.post(
            f"{SUNO_BASE_URL}/api/v1/generate",
            json=payload,
            headers=headers,
            timeout=30
        )
        return JSONResponse(r.json(), status_code=r.status_code)

    except Exception as e:
        logging.exception("Generate error")
        return JSONResponse(
            {"error": "suno_generate_failed", "message": str(e)},
            status_code=500
        )

# =====================================================
# CEK STATUS LAGU (AMBIL MP3)
# =====================================================
@app.get("/status/{task_id}")
def check_status(task_id: str):
    headers = {
        "Authorization": f"Bearer {SUNO_API_TOKEN}"
    }

    try:
        r = requests.get(
            f"{SUNO_BASE_URL}/api/v1/generate/record-info",
            params={"taskId": task_id},
            headers=headers,
            timeout=20
        )
        return JSONResponse(r.json(), status_code=r.status_code)

    except Exception as e:
        logging.exception("Status error")
        return JSONResponse(
            {"error": "status_failed", "message": str(e)},
            status_code=500
        )
