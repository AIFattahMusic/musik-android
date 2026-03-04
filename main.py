import os
import httpx
import requests
import uuid
import psycopg2
import json
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

# ===== TAMBAHAN FIREBASE =====
import firebase_admin
from firebase_admin import credentials, firestore

firebase_db = None
FIREBASE_CRED_JSON = os.getenv("FIREBASE_CRED_JSON")
if FIREBASE_CRED_JSON:
    cred = credentials.Certificate(json.loads(FIREBASE_CRED_JSON))
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    firebase_db = firestore.client()
# ===== END FIREBASE =====

# ==================================================
# WAJIB PALING ATAS: BUAT FOLDER MEDIA
# ==================================================
os.makedirs("media", exist_ok=True)

# ================= ENV =================
SUNO_API_KEY = os.getenv("SUNO_API_KEY")

BASE_URL = os.getenv(
    "BASE_URL",
    "https://musik-android.onrender.com"
)

CALLBACK_URL = f"{BASE_URL}/callback"

SUNO_BASE_API = "https://api.kie.ai/api/v1"
STYLE_GENERATE_URL = f"{SUNO_BASE_API}/style/generate"
MUSIC_GENERATE_URL = f"{SUNO_BASE_API}/generate"
STATUS_URL = f"{SUNO_BASE_API}/generate/record-info"
# Endpoint Baru
LYRICS_URL = f"{SUNO_BASE_API}/generate/get-timestamped-lyrics"
VIDEO_URL = f"{SUNO_BASE_API}/mp4/generate"

# ================= APP =================
app = FastAPI(
    title="AI Music Suno API Wrapper",
    version="1.0.4"
)

# ==================================================
# STATIC FILES
# ==================================================
app.mount("/media", StaticFiles(directory="media"), name="media")

# ================= REQUEST MODEL =================
class BoostStyleRequest(BaseModel):
    content: str


class GenerateMusicRequest(BaseModel):
    prompt: str
    style: Optional[str] = None
    title: Optional[str] = None
    instrumental: bool = False
    customMode: bool = False
    model: str = "V4_5"

# Model Baru untuk Lirik dan Video
class LyricRequest(BaseModel):
    taskId: str
    audioId: str

class VideoRequest(BaseModel):
    taskId: str
    audioId: str
    author: Optional[str] = "DJ Fattah"


# ================= HELPERS =================
def suno_headers():
    if not SUNO_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="SUNO_API_KEY not set in environment"
        )
    return {
        "Authorization": f"Bearer {SUNO_API_KEY}",
        "Content-Type": "application/json"
    }


def normalize_model(model: str) -> str:
    if model.lower() in ["v4", "v4_5", "v45"]:
        return "V4_5"
    return model


# ================= ENDPOINTS =================
@app.get("/")
def root():
    return {"status": "running", "service": "AI Music Suno API"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/boost-style")
async def boost_style(payload: BoostStyleRequest):
    async with httpx.AsyncClient(timeout=60) as client:
        res = await client.post(
            STYLE_GENERATE_URL,
            headers=suno_headers(),
            json={"content": payload.content}
        )
    return res.json()


@app.post("/generate-music")
async def generate_music(payload: GenerateMusicRequest):
    body = {
        "prompt": payload.prompt,
        "customMode": payload.customMode,
        "instrumental": payload.instrumental,
        "model": normalize_model(payload.model),
        "callBackUrl": CALLBACK_URL
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


@app.get("/record-info/{task_id}")
async def record_info(task_id: str):
    async with httpx.AsyncClient(timeout=30) as client:
     audio_url = data["data"]["response"]["sunoData"][0]["audioUrl"]

if audio_url:
    file_id = str(uuid.uuid4())
    audio_path = f"songs/{file_id}.mp3"

    audio_bytes = requests.get(audio_url).content

    supabase.storage.from_("music").upload(
        audio_path,
        audio_bytes,
        {"upsert": True}
    )

    supabase.table("songs").insert({
        "title": data["data"]["response"]["sunoData"][0]["title"],
        "artist": "AI Generator",
        "genre": "AI",
        "lyrics": data["data"]["response"]["sunoData"][0]["prompt"],
        "audio_path": audio_path
    }).execute() res = await client.get(
            STATUS_URL,
            headers=suno_headers(),
            params={"taskId": task_id}
        )
    return res.json()

# --- ENDPOINT BARU UNTUK LIRIK ---
@app.post("/get-timestamped-lyrics")
async def get_lyrics(payload: LyricRequest):
    async with httpx.AsyncClient(timeout=60) as client:
        res = await client.post(
            LYRICS_URL,
            headers=suno_headers(),
            json=payload.dict()
        )
    return res.json()

# --- ENDPOINT BARU UNTUK VIDEO ---
@app.post("/generate-video")
async def generate_video(payload: VideoRequest):
    body = payload.dict()
    body.update({
        "callBackUrl": CALLBACK_URL,
        "domainName": BASE_URL.replace("https://", "").replace("http://", "")
    })
    async with httpx.AsyncClient(timeout=60) as client:
        res = await client.post(
            VIDEO_URL,
            headers=suno_headers(),
            json=body
        )
    return res.json()


from fastapi import Request
import uuid
import requests

@app.post("/callback")
async def callback(request: Request):
    data = await request.json()

    print("CALLBACK MASUK")

    audio_url = data.get("audio_url")
    lyrics = data.get("lyrics", "")
    title = data.get("title", "Untitled")
    artist = "AI Generator"
    genre = "AI"

    if not audio_url:
        print("TIDAK ADA AUDIO URL")
        return {"status": "no audio"}

    try:
        file_id = str(uuid.uuid4())
        audio_path = f"songs/{file_id}.mp3"

        print("DOWNLOAD AUDIO")
        audio_bytes = requests.get(audio_url).content

        print("UPLOAD KE SUPABASE")
        supabase.storage.from_("music").upload(
            audio_path,
            audio_bytes,
            {"upsert": True}
        )

        print("SIMPAN DATABASE")
        supabase.table("songs").insert({
            "title": title,
            "artist": artist,
            "genre": genre,
            "lyrics": lyrics,
            "audio_path": audio_path
        }).execute()

        print("SELESAI")

        return {"status": "saved"}

    except Exception as e:
        print("ERROR:", e)
        return {"error": str(e)}

    task_id = data.get("taskId") or data.get("task_id")
    items = data.get("data") or []

    if not task_id or not items:
        return {"status": "ignored"}

    item = items[0]
    state = item.get("state") or item.get("status")

    if state != "succeeded":
        return {"status": "processing"}

    audio_url = (
        item.get("audio_url")
        or item.get("audioUrl")
        or item.get("audio")
        or item.get("streamAudioUrl")
    )

    if not audio_url:
        return {"status": "no_audio"}

    title = item.get("title", "Untitled")
    image_url = item.get("imageUrl")
    lyrics = item.get("lyrics")

    # SAVE MP3
    try:
        audio_bytes = requests.get(audio_url).content
        file_path = f"media/{task_id}.mp3"
        with open(file_path, "wb") as f:
            f.write(audio_bytes)
        local_audio_url = f"{BASE_URL}/media/{task_id}.mp3"
    except:
        local_audio_url = audio_url

    # POSTGRES (TETAP)
    try:
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO songs (task_id, title, audio_url, cover_url, lyrics, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (task_id) DO NOTHING
            """,
            (task_id, title, local_audio_url, image_url, lyrics, "done")
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Postgres Error: {e}")

    # FIREBASE (TAMBAHAN)
    if firebase_db:
        try:
            firebase_db.collection("songs_api").document(task_id).set({
                "task_id": task_id,
                "title": title,
                "audio_url": local_audio_url,
                "cover_url": image_url,
                "lyrics": lyrics,
                "status": "done"
            })
        except Exception as e:
            print(f"Firebase Error: {e}")

    return {"status": "saved"}


# ================= DB TEST =================
def get_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])


@app.get("/db-all")
def db_all():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM information_schema.tables
        WHERE table_schema = 'public';
        """
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

from fastapi import UploadFile, File, Form

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

    # upload ke bucket "music"
    supabase.storage.from_("music").upload(audio_path, audio_bytes)
    supabase.storage.from_("music").upload(cover_path, cover_bytes)

    # simpan ke database
    supabase.table("songs").insert({
        "title": title,
        "artist": artist,
        "genre": genre,
        "lyrics": lyrics,
        "audio_path": audio_path,
        "cover_path": cover_path
    }).execute()

    return {"status": "success"}

@app.post("/callback")
async def callback(request: Request):
    try:
        data = await request.json()

        print("Callback data:", data)

        audio_url = data.get("audio_url")
        lyrics = data.get("lyrics", "")
        title = data.get("title", "Untitled")
        artist = "AI Generator"
        genre = "AI"

        if audio_url:
            file_id = str(uuid.uuid4())
            audio_path = f"songs/{file_id}.mp3"

            # download mp3 dari suno
            audio_bytes = requests.get(audio_url).content

            # upload ke storage bucket "music"
            supabase.storage.from_("music").upload(
                audio_path,
                audio_bytes
            )

            # simpan ke database
            supabase.table("songs").insert({
                "title": title,
                "artist": artist,
                "genre": genre,
                "lyrics": lyrics,
                "audio_path": audio_path,
                "cover_path": None
            }).execute()

            print("SUCCESS SAVE TO SUPABASE")

        return {"status": "ok"}

    except Exception as e:
        print("CALLBACK ERROR:", e)
        return {"status": "error", "message": str(e)}

@app.get("/record-info/{task_id}")
async def record_info(task_id: str):
    try:
        # ambil hasil dari Suno
        url = f"https://api.sunoapi.org/api/v1/generate/record-info?taskId={task_id}"
        headers = {"Authorization": f"Bearer {SUNO_API_KEY}"}
        res = requests.get(url, headers=headers)
        data = res.json()

        # ambil audioUrl
        record = data.get("data", {})
        audio_url = record.get("audioUrl")
        title = record.get("title", "Untitled")
        lyrics = record.get("lyrics", "")
        artist = "AI Generator"
        genre = "AI"

        if audio_url:
            import uuid

            file_id = str(uuid.uuid4())
            audio_path = f"songs/{file_id}.mp3"

            # download mp3 dari Suno
            audio_bytes = requests.get(audio_url).content

            # upload ke Supabase bucket "music"
            supabase.storage.from_("music").upload(
                audio_path,
                audio_bytes
            )

            # simpan ke table songs
            supabase.table("songs").insert({
                "title": title,
                "artist": artist,
                "genre": genre,
                "lyrics": lyrics,
                "audio_path": audio_path,
                "cover_path": None
            }).execute()

        return data

    except Exception as e:
        return {"error": str(e)}



