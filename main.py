import os
import httpx
import requests
import firebase_admin
from firebase_admin import credentials, firestore
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import time
import json

# ==================================================
# KONFIGURASI FOLDER & ENV
# ==================================================
os.makedirs("media", exist_ok=True)

SUNO_API_KEY = os.getenv("SUNO_API_KEY")
BASE_URL = os.getenv("BASE_URL", "https://musik-android.onrender.com")
CALLBACK_URL = f"{BASE_URL}/callback"

# ==================================================
# KONEKSI FIREBASE (ADMIN SDK)
# ==================================================
# Cara 1: Ambil dari Environment Variable (Rekomendasi untuk Render)
firebase_config = os.getenv("FIREBASE_SERVICE_ACCOUNT")

if firebase_config:
    try:
        cred = credentials.Certificate(json.loads(firebase_config))
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("✅ Firebase Connected via ENV")
    except Exception as e:
        print(f"❌ Firebase Error: {e}")
        db = None
else:
    # Cara 2: Pakai file lokal (untuk testing di komputer)
    try:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("✅ Firebase Connected via JSON File")
    except:
        db = None
        print("⚠️ Firebase NOT Connected. Set FIREBASE_SERVICE_ACCOUNT env var!")

# ==================================================
# APP INIT
# ==================================================
app = FastAPI(title="Fattah AI Music - Firebase Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/media", StaticFiles(directory="media"), name="media")

class GenerateRequest(BaseModel):
    prompt: str
    userId: Optional[str] = None
    style: Optional[str] = None
    title: Optional[str] = None
    instrumental: bool = False
    customMode: bool = False
    model: str = "V4_5"

def save_file(url: str, filename: str):
    try:
        r = requests.get(url, timeout=60)
        with open(f"media/{filename}", "wb") as f:
            f.write(r.content)
        return f"{BASE_URL}/media/{filename}"
    except:
        return url

# ==================================================
# ENDPOINTS
# ==================================================

@app.get("/")
def health():
    return {"status": "online", "firebase_connected": db is not None}

@app.post("/generate-music")
async def generate_music(payload: GenerateRequest):
    headers = {"Authorization": f"Bearer {SUNO_API_KEY}", "Content-Type": "application/json"}
    body = {
        "prompt": payload.prompt,
        "customMode": payload.customMode,
        "instrumental": payload.instrumental,
        "model": payload.model,
        "callBackUrl": CALLBACK_URL
    }
    if payload.style: body["style"] = payload.style
    if payload.title: body["title"] = payload.title

    async with httpx.AsyncClient(timeout=60) as client:
        res = await client.post("https://api.kie.ai/api/v1/generate", headers=headers, json=body)
    
    data = res.json()
    
    # Simpan data awal ke Firestore agar muncul "Processing" di app
    if db and res.status_code == 200 and data.get("data"):
        task_id = data["data"].get("taskId")
        if task_id:
            db.collection("songs").document(task_id).set({
                "taskId": task_id,
                "userId": payload.userId,
                "title": payload.title or "Untitled",
                "style": payload.style,
                "lyrics": payload.prompt,
                "status": "processing",
                "createdAt": int(time.time() * 1000)
            }, merge=True)

    return data

@app.post("/callback")
async def callback(request: Request):
    payload = await request.json()
    task_id = payload.get("taskId")
    items = payload.get("data", [])
    
    if not items or not db:
        return {"status": "ignored"}
    
    item = items[0]
    if item.get("state") == "succeeded":
        audio_url = item.get("audioUrl") or item.get("streamAudioUrl")
        if audio_url:
            # Simpan file ke server Anda (Opsional)
            local_audio = save_file(audio_url, f"{task_id}.mp3")
            
            # Update data di Firestore
            db.collection("songs").document(task_id).update({
                "audioUrl": local_audio,
                "imageUrl": item.get("imageUrl"),
                "duration": item.get("duration"),
                "status": "completed"
            })
            print(f"✅ Song {task_id} completed and updated in Firestore")
            return {"status": "success"}
            
    return {"status": "processing"}


