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
    style: str = ""
    title: str = "False"
    customMode: bool = False
    instrumental: bool = False
    model: str = "V4_5"
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
