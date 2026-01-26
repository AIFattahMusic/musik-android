import os
import requests
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psycopg2

# =========================
# APP
# =========================
app = FastAPI()

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
SUNO_API_CREATE_URL = os.getenv(
    "SUNO_API_CREATE_URL",
    "https://api.sunoapi.org/api/v1/generate"
)
SUNO_API_STATUS_URL = os.getenv(
    "SUNO_API_STATUS_URL",
    "https://api.sunoapi.org/api/v1/status"
)
SUNO_TOKEN = os.getenv("SUNO_TOKEN")

BASE_URL = os.getenv(
    "BASE_URL",
    "https://musik-android.onrender.com"
)

HEADERS = {
    "Authorization": f"Bearer {SUNO_TOKEN}",
    "Content-Type": "application/json",
}

# =========================
# REQUEST MODEL
# =========================
class GenerateRequest(BaseModel):
    prompt: str
    tags: str = ""
    custom_mode: bool = False
    instrumental: bool = False
    model: str = "V4_5"

# =========================
# HEALTH CHECK
# =========================
@app.get("/")
def root():
    return {"status": "ok"}

# =========================
# GENERATE SONG (FIXED)
# =========================
@app.post("/generate/full-song")
def generate_full_song(data: GenerateRequest):
    if not SUNO_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="SUNO_TOKEN belum diset di Render"
        )

    payload = {
        "prompt": data.prompt,
        "tags": data.tags,
        "custom_mode": data.custom_mode,
        "instrumental": data.instrumental,
        "model": data.model,
        # 🔴 INI WAJIB
        "callBackUrl": f"{BASE_URL}/callback",
    }

    try:
        r = requests.post(
            SUNO_API_CREATE_URL,
            headers=HEADERS,
            json=payload,
            timeout=60,
        )

        return r.json()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =========================
# CALLBACK ENDPOINT

@app.get("/generate/status/{task_id}")
def generate_status(task_id: str):
    return {
        "task_id": task_id,
        "status": "processing"
    }
