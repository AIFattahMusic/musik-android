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
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Supabase Connected")
    except Exception as e:
        print(f"❌ Supabase Connection Error: {e}")

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
        if os.path.exists("serviceAccountKey.json"):
            cred = credentials.Certificate("serviceAccountKey.json")
            firebase_admin.initialize_app(cred)
            db = firestore.client()
            print("✅ Firebase Connected via JSON File")
        else:
            db = None
            print("⚠️ Firebase NOT Connected. Set FIREBASE_SERVICE_ACCOUNT env var!")
    except Exception as e:
        db = None
        print(f"❌ Firebase Error: {e}")

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
    """Mengunduh file dari URL ke folder lokal media/"""
    try:
        path = f"media/{filename}"
        r = requests.get(url, timeout=60)
        with open(path, "wb") as f:
            f.write(r.content)
        return path
    except Exception as e:
        print(f"❌ Error saving file: {e}")
        return None

# ================= SUPABASE UPLOAD =================
def upload_to_supabase(file_path, filename):
    """Mengunggah file dari lokal ke Supabase Storage"""
    if not supabase:
        return None

    try:
        with open(file_path, "rb") as f:
            # Menggunakan upsert=True agar jika file sudah ada akan ditimpa (menghindari error)
            supabase.storage.from_("music").upload(
                path=filename, 
                file=f, 
                file_options={"x-upsert": "true", "content-type": "audio/mpeg"}
            )

        res = supabase.storage.from_("music").get_public_url(filename)
        return res
    except Exception as e:
        print("❌ Supabase upload error:", e)
        return None

# ================= ENDPOINTS =================

@app.get("/")
def health():
    return {
        "status": "online", 
        "firebase_connected": db is not None,
        "supabase_connected": supabase is not None,
        "base_url": BASE_URL
    }

@app.post("/generate-music")
async def generate_music(payload: GenerateRequest):
    if not SUNO_API_KEY:
        raise HTTPException(status_code=500, detail="SUNO_API_KEY tidak diatur")

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
    
    if res.status_code != 200:
        return res.json()

    data = res.json()
    
    # Simpan data awal ke koleksi 'songs' dan 'global_songs' agar statusnya 'processing'
    if db and data.get("data"):
        task_id = data["data"].get("taskId")
        if task_id:
            song_data = {
                "id": task_id,
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
        raise HTTPException(status_code=res.status_code, detail="Gagal mengambil info")
        
    return res.json()

@app.post("/callback")
async def callback(request: Request):
    payload = await request.json()
    print(f"🔔 CALLBACK RECEIVED for Task: {payload.get('taskId')}")
    
    task_id = payload.get("taskId")
    items = payload.get("data", [])
    
    if not items or not db or not task_id:
        return {"status": "ignored"}
    
    item = items[0]
    state = str(item.get("state", "")).lower()
    
    if state in ["succeeded", "success", "completed"]:
        audio_url = item.get("audioUrl") or item.get("streamAudioUrl")
        if audio_url:
            filename = f"{task_id}.mp3"
            
            # 1. Download file ke server lokal
            local_path = save_file(audio_url, filename)
            
            # 2. Upload ke Supabase Storage
            supabase_url = None
            if local_path:
                supabase_url = upload_to_supabase(local_path, filename)

            # URL Final: Utamakan Supabase, jika gagal gunakan Local, jika gagal gunakan Original
            final_audio_url = supabase_url or f"{BASE_URL}/media/{filename}" if local_path else audio_url

            update_data = {
                "audioUrl": final_audio_url,
                "imageUrl": item.get("imageUrl") or item.get("image_url"),
                "duration": item.get("duration") or 0,
                "lyrics": item.get("lyrics") or item.get("prompt"),
                "style": item.get("tags") or "AI Music",
                "status": "completed"
            }
            
            # Update di Firestore
            db.collection("songs").document(task_id).update(update_data)
            db.collection("global_songs").document(task_id).update(update_data)
            
            print(f"✅ Task {task_id} marked as COMPLETED. Audio: {final_audio_url}")
            return {"status": "success"}
            
    return {"status": "processing"}
