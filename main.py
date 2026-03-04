import os
import httpx
import requests
import psycopg2
import psycopg2.extras
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import time

# ==================================================
# KONFIGURASI FOLDER & ENV
# ==================================================
os.makedirs("media", exist_ok=True)

SUNO_API_KEY = os.getenv("SUNO_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

# Fix untuk library psycopg2/SQLAlchemy yang butuh postgresql://
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

BASE_URL = os.getenv("BASE_URL", "https://musik-android.onrender.com")
CALLBACK_URL = f"{BASE_URL}/callback"

SUNO_BASE_API = "https://api.kie.ai/api/v1"
MUSIC_GENERATE_URL = f"{SUNO_BASE_API}/generate"
STATUS_URL = f"{SUNO_BASE_API}/generate/record-info"
VIDEO_URL = f"{SUNO_BASE_API}/mp4/generate"

app = FastAPI(title="Fattah AI Music API", version="2.5.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/media", StaticFiles(directory="media"), name="media")

# ==================================================
# DATABASE HELPERS
# ==================================================
def get_conn():
    if not DATABASE_URL:
        raise Exception("DATABASE_URL tidak ditemukan di Environment Variables")
    return psycopg2.connect(DATABASE_URL)

def init_db():
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS songs (
                id SERIAL PRIMARY KEY,
                task_id TEXT UNIQUE,
                user_id TEXT,
                title TEXT,
                audio_url TEXT,
                cover_url TEXT,
                lyrics TEXT,
                style TEXT,
                duration DOUBLE PRECISION,
                status TEXT,
                audio_id TEXT,
                video_task_id TEXT,
                video_url TEXT,
                created_at BIGINT
            );
        """)
        conn.commit()
        cur.close()
        conn.close()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Gagal inisialisasi database: {e}")

@app.on_event("startup")
def startup():
    init_db()

# ================= REQUEST MODELS =================
class GenerateMusicRequest(BaseModel):
    prompt: str
    userId: Optional[str] = "public"
    style: Optional[str] = None
    title: Optional[str] = None
    instrumental: bool = False
    customMode: bool = False
    model: str = "V4_5"

# ================= HELPERS =================
def save_remote_file(url: str, filename: str):
    try:
        r = requests.get(url, timeout=60)
        with open(f"media/{filename}", "wb") as f:
            f.write(r.content)
        return f"{BASE_URL}/media/{filename}"
    except:
        return url

# ================= ENDPOINTS =================

@app.get("/")
def home():
    return {"status": "online", "db_connected": DATABASE_URL is not None}

@app.post("/generate-music")
async def generate_music(payload: GenerateMusicRequest):
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
        res = await client.post(MUSIC_GENERATE_URL, headers=headers, json=body)
    
    data = res.json()
    
    if res.status_code == 200 and data.get("data"):
        task_id = data["data"].get("taskId")
        if task_id:
            try:
                conn = get_conn()
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO songs (task_id, user_id, title, style, lyrics, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (task_id) DO NOTHING
                """, (task_id, payload.userId, payload.title, payload.style, payload.prompt, "processing", int(time.time() * 1000)))
                conn.commit()
                cur.close()
                conn.close()
            except Exception as e:
                print(f"DB Error: {e}")

    return data

@app.post("/callback")
async def callback(request: Request):
    try:
        payload = await request.json()
        task_id = payload.get("taskId")
        items = payload.get("data", [])
        
        if not items: return {"status": "no_data"}
        
        item = items[0]
        if item.get("state") != "succeeded": return {"status": "not_ready"}

        audio_url = item.get("audioUrl") or item.get("streamAudioUrl")
        
        if audio_url:
            local_audio = save_remote_file(audio_url, f"{task_id}.mp3")
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("""
                UPDATE songs SET 
                    audio_url = %s,
                    cover_url = %s,
                    audio_id = %s,
                    status = 'completed'
                WHERE task_id = %s
            """, (local_audio, item.get("imageUrl"), item.get("audioId"), task_id))
            conn.commit()
            cur.close()
            conn.close()
            return {"status": "success"}
    except Exception as e:
        print(f"Callback Error: {e}")
    return {"status": "ignored"}

@app.get("/get-songs")
def get_songs(user_id: Optional[str] = None):
    try:
        conn = get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if user_id:
            cur.execute("SELECT * FROM songs WHERE user_id = %s OR user_id = 'public' ORDER BY id DESC", (user_id,))
        else:
            cur.execute("SELECT * FROM songs WHERE status = 'completed' ORDER BY id DESC LIMIT 50")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        return {"error": str(e)}

@app.get("/record-info/{task_id}")
async def get_info(task_id: str):
    headers = {"Authorization": f"Bearer {SUNO_API_KEY}"}
    async with httpx.AsyncClient() as client:
        res = await client.get(STATUS_URL, headers=headers, params={"taskId": task_id})
    return res.json()
