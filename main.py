import os
import httpx
import requests
import uuid
import psycopg2
import json
from supabase import create_client
from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

# ================= ENV =================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUNO_API_KEY = os.getenv("SUNO_API_KEY")
BASE_URL = os.getenv("BASE_URL", "https://musik-android.onrender.com")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Supabase ENV missing")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ================= FIREBASE =================

import firebase_admin
from firebase_admin import credentials, firestore

firebase_db = None
FIREBASE_CRED_JSON = os.getenv("FIREBASE_CRED_JSON")

if FIREBASE_CRED_JSON:
    cred = credentials.Certificate(json.loads(FIREBASE_CRED_JSON))
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    firebase_db = firestore.client()

# ================= SUNO =================

SUNO_BASE_API = "https://api.kie.ai/api/v1"
MUSIC_GENERATE_URL = f"{SUNO_BASE_API}/generate"
STATUS_URL = f"{SUNO_BASE_API}/generate/record-info"

def suno_headers():
    return {
        "Authorization": f"Bearer {SUNO_API_KEY}",
        "Content-Type": "application/json"
    }

# ================= APP =================

app = FastAPI(title="AI Music Suno API Wrapper")

os.makedirs("media", exist_ok=True)
app.mount("/media", StaticFiles(directory="media"), name="media")

# ================= MODEL =================

class GenerateMusicRequest(BaseModel):
    prompt: str
    style: Optional[str] = None
    title: Optional[str] = None
    instrumental: bool = False
    customMode: bool = False
    model: str = "V4_5"

# ================= ROOT =================

@app.get("/")
def root():
    return {"status": "running"}

# ================= GENERATE =================

@app.post("/generate-music")
async def generate_music(payload: GenerateMusicRequest):

    body = {
        "prompt": payload.prompt,
        "customMode": payload.customMode,
        "instrumental": payload.instrumental,
        "model": payload.model
    }

    if payload.style:
        body["style"] = payload.style
    if payload.title:
        body["title"] = payload.title

    async with httpx.AsyncClient(timeout=60) as client:
        res = await client.post(
            MUSIC_GENERATE_URL,
            headers=suno_headers(),
            json=body
        )

    if res.status_code != 200:
        raise HTTPException(status_code=500, detail=res.text)

    return res.json()

# ================= RECORD INFO + AUTO SAVE =================

@app.get("/record-info/{task_id}")
async def record_info(task_id: str):

    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.get(
            STATUS_URL,
            headers=suno_headers(),
            params={"taskId": task_id}
        )

    data = res.json()

    try:
        suno_data = data["data"]["response"]["sunoData"][0]
        audio_url = suno_data.get("audioUrl")

        if not audio_url:
            return {"status": "processing", "data": data}

        title = suno_data.get("title", "Untitled")
        lyrics = suno_data.get("prompt", "")
        image_url = suno_data.get("imageUrl")

        # Download MP3
        audio_bytes = requests.get(audio_url).content
        file_id = str(uuid.uuid4())
        audio_path = f"songs/{file_id}.mp3"

        # Upload Supabase
        supabase.storage.from_("music").upload(
            audio_path,
            audio_bytes,
            {"upsert": True}
        )

        # Insert Supabase Table
        supabase.table("songs").insert({
            "title": title,
            "artist": "AI Generator",
            "genre": "AI",
            "lyrics": lyrics,
            "audio_path": audio_path,
            "cover_path": image_url
        }).execute()

        # Postgres
        try:
            conn = psycopg2.connect(os.environ["DATABASE_URL"])
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO songs (task_id, title, audio_url, cover_url, lyrics, status)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (task_id) DO NOTHING
                """,
                (task_id, title, audio_path, image_url, lyrics, "done")
            )
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            print("Postgres error:", e)

        # Firebase
        if firebase_db:
            firebase_db.collection("songs_api").document(task_id).set({
                "task_id": task_id,
                "title": title,
                "audio_url": audio_path,
                "cover_url": image_url,
                "lyrics": lyrics,
                "status": "done"
            })

        return {"status": "saved", "audio_path": audio_path}

    except Exception as e:
        return {"error": str(e)}

# ================= MANUAL UPLOAD =================

@app.post("/upload-song")
async def upload_song(
    title: str = Form(...),
    artist: str = Form(...),
    genre: str = Form(...),
    lyrics: str = Form(...),
    audio: UploadFile = File(...),
    cover: UploadFile = File(...)
):
    audio_bytes = await audio.read()
    cover_bytes = await cover.read()

    audio_path = f"songs/{audio.filename}"
    cover_path = f"covers/{cover.filename}"

    supabase.storage.from_("music").upload(audio_path, audio_bytes, {"upsert": True})
    supabase.storage.from_("music").upload(cover_path, cover_bytes, {"upsert": True})

    supabase.table("songs").insert({
        "title": title,
        "artist": artist,
        "genre": genre,
        "lyrics": lyrics,
        "audio_path": audio_path,
        "cover_path": cover_path
    }).execute()

    return {"status": "success"}
