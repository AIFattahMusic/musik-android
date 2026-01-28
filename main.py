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
    title: str                    # JUDUL
    prompt: str                   # DESKRIPSI
    lyrics: str                   # LIRIK FULL
    tags: str | None = None
    model: str = "v3_5"

# =====================================================
# HEALTH CHECK
# =====================================================
@app.get("/")
def root():
    return {"status": "ok"}

# =====================================================
# GENERATE FULL SONG
# =====================================================
@app.post("/generate/full-song")
def generate_full_song(data: GenerateRequest):
     payload = {
    "title": data.title or "Untitled Song",
    "prompt": data.prompt or "Create a song",
    "tags": data.tags or "reggae",
    "customMode": False,
    "instrumental": False,
    "callBackUrl": f"{BASE_URL}/callback"
}


    try:
        r = requests.post(
            SUNO_API_GENERATE_URL,
            headers=HEADERS,
            json=payload,
            timeout=60,
        )
    except requests.RequestException as e:
        raise HTTPException(502, f"Gagal koneksi ke Suno: {e}")

    if r.status_code >= 400:
    raise HTTPException(r.status_code, r.text)

    res = r.json()
    if res.get("code") != 200:
        raise HTTPException(500, res.get("msg", "Generate gagal"))

    return res

# =====================================================
# CALLBACK SUNO (FULL AKTIF)
# =====================================================
@app.post("/callback")
async def callback(request: Request):
    body = await request.body()
    if not body:
        return {"ok": True}

    data = await request.json()

    if data.get("status") == "completed":
        DB.append({
            "task_id": data.get("id"),
            "title": data.get("title"),
            "audio_url": data.get("audio_url"),
            "image_url": data.get("image_url"),
        })

    return {"ok": True}

    data = payload.get("data", {})
    task_id = data.get("task_id")
    items = data.get("data", [])

    if not task_id or not items:
        return {"status": "invalid_payload"}

    item = items[0]

    audio_url = (
        item.get("audio_url")
        or item.get("audioUrl")
        or item.get("audio")
    )

    if not audio_url:
        return {"status": "no_audio"}

    mp3_path = f"{GENERATED_DIR}/{task_id}.mp3"

    # Idempotent (aman kalau callback dipanggil ulang)
    if os.path.exists(mp3_path):
        return {"status": "already_saved"}

    try:
        audio_resp = requests.get(audio_url, timeout=60)
        if audio_resp.status_code != 200:
            return {"status": "download_failed"}

        with open(mp3_path, "wb") as f:
            f.write(audio_resp.content)

    except Exception as e:
        return {"status": "error", "detail": str(e)}

    return {
        "status": "saved",
        "task_id": task_id,
    }

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

# =====================================================
# DOWNLOAD MP3
# =====================================================
@app.get("/generate/download/{task_id}")
def download_mp3(task_id: str):
    path = f"{GENERATED_DIR}/{task_id}.mp3"

    if not os.path.exists(path):
        raise HTTPException(404, "File belum tersedia")

    return FileResponse(
        path,
        media_type="audio/mpeg",
        filename=f"{task_id}.mp3",
    )

# ======================
# CONFIG
# ======================
SUNO_API_URL = os.getenv("SUNO_API_URL", "https://api.sunoapi.org/api/v1/generate")
SUNO_TOKEN = os.getenv("SUNO_TOKEN", "")
CALLBACK_URL = "https://musik-android.onrender.com/callback"

HEADERS = {
    "Authorization": f"Bearer {SUNO_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# ======================
# DB SEDERHANA (AUTO ISI)
# ======================
DB = []   # restart server = reset (normal untuk sekarang)

# ======================
# GENERATE (TEST DULU)
# ======================
@app.post("/generate")
def generate(prompt: str):
    payload = {
        "prompt": prompt,
        "callback_url": CALLBACK_URL
    }

    r = requests.post(
        SUNO_API_URL,
        json=payload,
        headers=HEADERS,
        timeout=60
    )

    resp = r.json()

    return {
        "status": "sent",
        "suno_status": r.status_code,
        "suno_response": resp
    }

# ======================
# CALLBACK (AUTO SIMPAN)
# ======================
@app.post("/callback")
async def callback(request: Request):
    body = await request.body()
    if not body:
        return {"ok": True}

    data = await request.json()

    if data.get("status") == "completed":
        DB.append({
            "task_id": data.get("id"),
            "title": data.get("title"),
            "audio_url": data.get("audio_url"),
            "image_url": data.get("image_url"),
        })

    return {"ok": True}

# ======================
# CEK ISI DB
# ======================
@app.get("/db-all")
def db_all():
    return DB if DB else []










