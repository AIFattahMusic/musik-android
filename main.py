import os
import httpx
import requests
import firebase_admin
from firebase_admin import credentials, firestore
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import time
import json
from supabase import create_client

# ==================================================
# KONFIGURASI FOLDER & ENV
# ==================================================
os.makedirs("media", exist_ok=True)

SUNO_API_KEY = os.getenv("SUNO_API_KEY")
BASE_URL = os.getenv("BASE_URL", "https://musik-android.onrender.com")
CALLBACK_URL = f"{BASE_URL}/callback"

# SUPABASE CONFIG
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Supabase Connected")

# ==================================================
# KONEKSI FIREBASE (ADMIN SDK)
# ==================================================
firebase_config = os.getenv("FIREBASE_SERVICE_ACCOUNT")

if firebase_config:
    try:
        cred_dict = json.loads(firebase_config)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("✅ Firebase Connected via ENV")
    except Exception as e:
        print(f"❌ Firebase Error: {e}")
        db = None
else:
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

# ================= REQUEST MODELS =================
class GenerateRequest(BaseModel):
    prompt: str
    userId: Optional[str] = None
    style: Optional[str] = None
    title: Optional[str] = None
    instrumental: bool = False
    customMode: bool = False
    model: str = "V4_5"

# ================= HELPERS =================
def save_file(url: str, filename: str):
    try:
        r = requests.get(url, timeout=60)
        with open(f"media/{filename}", "wb") as f:
            f.write(r.content)
        return f"{BASE_URL}/media/{filename}"
    except:
        return url


# ================= SUPABASE UPLOAD =================
def upload_to_supabase(file_path, filename):
    if not supabase:
        return None

    try:
        with open(file_path, "rb") as f:
            supabase.storage.from_("music").upload(filename, f)

        public_url = supabase.storage.from_("music").get_public_url(filename)
        return public_url
    except Exception as e:
        print("❌ Supabase upload error:", e)
        return None


# ================= ENDPOINTS =================

@app.get("/")
def health():
    return {
        "status": "online", 
        "firebase_connected": db is not None,
        "base_url": BASE_URL
    }

@app.post("/generate-music")
async def generate_music(payload: GenerateRequest):
    headers = {
        "Authorization": f"Bearer {SUNO_API_KEY}", 
        "Content-Type": "application/json"
    }
    
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
    
    # Simpan data awal ke koleksi 'songs' dan 'global_songs'
    if db and res.status_code == 200 and data.get("data"):
        task_id = data["data"].get("taskId")
        if task_id:
            song_data = {
                "taskId": task_id,
                "userId": payload.userId,
                "title": payload.title or "Untitled",
                "style": payload.style or "AI Music",
                "lyrics": payload.prompt,
                "status": "processing",
                "createdAt": int(time.time() * 1000)
            }
            db.collection("songs").document(task_id).set(song_data, merge=True)
            db.collection("global_songs").document(task_id).set(song_data, merge=True)

    return data


@app.get("/record-info/{task_id}")
async def record_info(task_id: str):
    headers = {"Authorization": f"Bearer {SUNO_API_KEY}"}
    params = {"taskId": task_id}
    
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.get("https://api.kie.ai/api/v1/generate/record-info", headers=headers, params=params)
    
    if res.status_code != 200:
        raise HTTPException(status_code=res.status_code, detail="Gagal mengambil info dari provider")
        
    return res.json()


@app.post("/callback")
async def callback(request: Request):
    payload = await request.json()
    print(f"CALLBACK RECEIVED: {payload}")
    
    task_id = payload.get("taskId")
    items = payload.get("data", [])
    
    if not items or not db:
        return {"status": "ignored"}
    
    item = items[0]
    state = str(item.get("state", "")).lower()
    
    if state in ["succeeded", "success", "completed"]:
        audio_url = item.get("audioUrl") or item.get("streamAudioUrl")
        if audio_url:

            # download audio
            local_audio = save_file(audio_url, f"{task_id}.mp3")

            # upload ke supabase storage otomatis
            supabase_url = upload_to_supabase(f"media/{task_id}.mp3", f"{task_id}.mp3")

            style_value = item.get("tags")

            update_data = {
                "audioUrl": supabase_url or local_audio,
                "imageUrl": item.get("imageUrl") or item.get("image_url"),
                "duration": item.get("duration") or 0,
                "lyrics": item.get("lyrics") or item.get("prompt"),
                "style": style_value,
                "status": "completed"
            }
            
            db.collection("songs").document(task_id).update(update_data)
            db.collection("global_songs").document(task_id).update(update_data)
            
            print(f"✅ Task {task_id} marked as COMPLETED in Firestore")
            return {"status": "success"}
            
    return {"status": "processing"}
