import os
import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

# =====================================================
# APP
# =====================================================
app = FastAPI(title="Suno Music Render API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================================================
# BASE URL (WAJIB URL RENDER ANDA)
# =====================================================
BASE_URL = os.getenv(
    "BASE_URL",
    "https://musik-android.onrender.com"
)

# =====================================================
# SUNO CONFIG
# =====================================================
SUNO_API_GENERATE_URL = "https://api.sunoapi.org/api/v1/generate"
SUNO_TOKEN = os.getenv("SUNO_TOKEN")

if not SUNO_TOKEN:
    raise RuntimeError("SUNO_TOKEN belum diset")

HEADERS = {
    "Authorization": f"Bearer {SUNO_TOKEN}",
    "Content-Type": "application/json",
}

# =====================================================
# STORAGE (RENDER)
# =====================================================
GENERATED_DIR = "generated"
os.makedirs(GENERATED_DIR, exist_ok=True)

# =====================================================
# MODEL
# =====================================================
class GenerateRequest(BaseModel):
    prompt: str
    tags: str | None = None
    custom_mode: bool = False
    instrumental: bool = False
    model: str = "V4_5"

# =====================================================
# HEALTH CHECK
# =====================================================
@app.get("/")
def root():
    return {"status": "ok"}

# =========================
# GENERATE FULL SONG
# =========================
@app.post("/generate/full-song")
def generate_full_song(data: GenerateRequest):
    task_id = uuid.uuid4().hex

    # ====== CONTOH GENERATE (GANTI DENGAN AI ANDA) ======
    title = f"Lagu tentang {data.prompt[:30]}"
    lyrics = f"Lirik lagu berdasarkan prompt:\n{data.prompt}"
    description = data.prompt

    # dummy file MP3
    mp3_path = f"{GENERATED_DIR}/{task_id}.mp3"
    with open(mp3_path, "wb") as f:
        f.write(b"")  # nanti ganti hasil audio asli

    # dummy cover image
    cover_path = f"{GENERATED_DIR}/{task_id}.jpg"
    with open(cover_path, "wb") as f:
        f.write(b"")  # nanti ganti hasil image asli

    # metadata
    metadata = {
        "task_id": task_id,
        "title": title,
        "lyrics": lyrics,
        "description": description,
        "cover_url": f"/generate/cover/{task_id}"
    }

    with open(f"{GENERATED_DIR}/{task_id}.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False)

    return {
        "task_id": task_id,
        "status": "generated"
    }


# =========================
# GET METADATA
# =========================
@app.get("/generate/metadata/{task_id}")
def get_metadata(task_id: str):
    path = f"{GENERATED_DIR}/{task_id}.json"

    if not os.path.exists(path):
        raise HTTPException(404, "Metadata tidak ditemukan")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# =========================
# DOWNLOAD MP3
# =========================
@app.get("/generate/download/{task_id}")
def download_mp3(task_id: str):
    path = f"{GENERATED_DIR}/{task_id}.mp3"

    if not os.path.exists(path):
        raise HTTPException(404, "File tidak ditemukan")

    return FileResponse(
        path,
        media_type="audio/mpeg",
        filename=f"{task_id}.mp3"
    )


# =========================
# GET COVER IMAGE
# =========================
@app.get("/generate/cover/{task_id}")
def get_cover(task_id: str):
    path = f"{GENERATED_DIR}/{task_id}.jpg"

    if not os.path.exists(path):
        raise HTTPException(404, "Cover tidak ditemukan")

    return FileResponse(
        path,
        media_type="image/jpeg",
        filename=f"{task_id}.jpg"
    )

# =====================================================
# STATUS (TANPA POLLING SUNO)
# =====================================================
@app.get("/generate/status/{task_id}")
def generate_status(task_id: str):
    mp3_path = f"{GENERATED_DIR}/{task_id}.mp3"

    if os.path.exists(mp3_path):
        return {
            "status": "done",
            "download_url": f"{BASE_URL}/generate/download/{task_id}",
        }

    return {"status": "processing"}

# =========================
# DOWNLOAD MP3
# =========================
@app.get("/generate/download/{task_id}")
def download_mp3(task_id: str):
    path = f"{GENERATED_DIR}/{task_id}.mp3"

    if not os.path.exists(path):
        raise HTTPException(404, "File belum tersedia")

    return FileResponse(
        path,
        media_type="audio/mpeg",
        filename=f"{task_id}.mp3"
    )


# =========================
# METADATA LAGU
# =========================
@app.get("/generate/metadata/{task_id}")
def get_metadata(task_id: str):
    return {
        "title": "Judul Lagu",
        "lyrics": "Ini lirik lagu...\nBaris kedua...\nBaris ketiga..."
    }


import os, psycopg2

def get_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])
@app.get("/db-all")
def db_all():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT *
        FROM information_schema.tables
        WHERE table_schema = 'public';
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows






