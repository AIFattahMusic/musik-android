import os
import json
import httpx
import requests

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

# ==================================================
# FIREBASE INIT (WAJIB PALING ATAS)
# ==================================================
import firebase_admin
from firebase_admin import credentials, firestore

firebase_cred_raw = os.getenv("FIREBASE_CRED")
if not firebase_cred_raw:
    raise RuntimeError("FIREBASE_CRED tidak ada di ENV")

cred_dict = json.loads(firebase_cred_raw)
cred = credentials.Certificate(cred_dict)

if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

db = firestore.client()
print("🔥 Firebase connected:", cred_dict["project_id"])

# ==================================================
# BASIC SETUP
# ==================================================
os.makedirs("media", exist_ok=True)

SUNO_API_KEY = os.getenv("SUNO_API_KEY")
BASE_URL = os.getenv("BASE_URL")
CALLBACK_URL = f"{BASE_URL}/callback"

SUNO_BASE_API = "https://api.kie.ai/api/v1"
MUSIC_GENERATE_URL = f"{SUNO_BASE_API}/generate"
STATUS_URL = f"{SUNO_BASE_API}/generate/record-info"

# ==================================================
# APP
# ==================================================
app = FastAPI(title="AI Music API", version="1.0.0")

app.mount("/media", StaticFiles(directory="media"), name="media")

# ==================================================
# MODELS
# ==================================================
class GenerateMusicRequest(BaseModel):
    prompt: str
    title: Optional[str] = None
    instrumental: bool = False
    model: str = "V4_5"

# ==================================================
# HELPERS
# ==================================================
def suno_headers():
    if not SUNO_API_KEY:
        raise HTTPException(500, "SUNO_API_KEY tidak ada")
    return {
        "Authorization": f"Bearer {SUNO_API_KEY}",
        "Content-Type": "application/json"
    }

# ==================================================
# ROUTES
# ==================================================
@app.get("/")
def root():
    return {"status": "ok"}

@app.post("/generate-music")
async def generate_music(payload: GenerateMusicRequest):
    body = {
        "prompt": payload.prompt,
        "instrumental": payload.instrumental,
        "model": payload.model,
        "callBackUrl": CALLBACK_URL
    }

    if payload.title:
        body["title"] = payload.title

    async with httpx.AsyncClient(timeout=60) as client:
        res = await client.post(
            MUSIC_GENERATE_URL,
            headers=suno_headers(),
            json=body
        )

    if res.status_code != 200:
        raise HTTPException(500, res.text)

    return res.json()

@app.get("/record-info/{task_id}")
async def record_info(task_id: str):
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.get(
            STATUS_URL,
            headers=suno_headers(),
            params={"taskId": task_id}
        )
    return res.json()

# ==================================================
# CALLBACK — INI YANG NYIMPEN KE FIRESTORE
# ==================================================
@app.post("/callback")
async def callback(request: Request):
    data = await request.json()

    task_id = data.get("taskId")
    items = data.get("data", [])

    if not task_id or not items:
        return {"status": "ignored"}

    item = items[0]

    if item.get("state") != "succeeded":
        return {"status": "processing"}

    audio_url = item.get("streamAudioUrl")
    image_url = item.get("imageUrl")
    lyrics = item.get("lyrics")
    title = item.get("title", "Untitled")

    if not audio_url:
        return {"status": "no_audio"}

    # ================= SAVE MP3 =================
    audio_bytes = requests.get(audio_url).content
    file_path = f"media/{task_id}.mp3"

    with open(file_path, "wb") as f:
        f.write(audio_bytes)

    local_audio_url = f"{BASE_URL}/media/{task_id}.mp3"

    # ================= SAVE FIRESTORE =================
    db.collection("songs_api").document(task_id).set({
        "task_id": task_id,
        "title": title,
        "audio_url": local_audio_url,
        "cover_url": image_url,
        "lyrics": lyrics,
        "status": "done",
        "created_at": firestore.SERVER_TIMESTAMP
    })

    print("✅ Saved to Firestore:", task_id)

    return {"status": "saved"}
