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

# =====================================================
# GENERATE FULL SONG
# =====================================================
@app.post("/generate/full-song")
def generate_full_song(data: GenerateRequest):
    payload = {
        "prompt": data.prompt,
        "tags": data.tags,
        "customMode": data.custom_mode,
        "instrumental": data.instrumental,
        "model": data.model,
        "callBackUrl": f"{BASE_URL}/generate/callback",
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

    if r.status_code != 200:
        raise HTTPException(r.status_code, r.text)

    res = r.json()
    if res.get("code") != 200:
        raise HTTPException(500, res.get("msg", "Generate gagal"))

    return res

# =====================================================
# CALLBACK SUNO (FULL AKTIF)
# =====================================================
@app.post("/generate/callback")
async def generate_callback(req: Request):
    payload = await req.json()

    # Validasi callback
    if payload.get("code") != 200:
        return {"status": "ignored"}

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
from fastapi import FastAPI, HTTPException
import os
import base64

app = FastAPI()

GENERATED_DIR = "generated"
lyrics_store = {
    # contoh
    # "task123": "Ini lirik lagunya..."
}

@app.get("/generate/result/{task_id}")
def get_result(task_id: str):
    path = f"{GENERATED_DIR}/{task_id}.mp3"

    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File belum tersedia")

    # baca mp3
    with open(path, "rb") as f:
        audio_bytes = f.read()

    audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

    return {
        "task_id": task_id,
        "lyrics": lyrics_store.get(task_id, ""),
        "audio_base64": audio_base64,
        "audio_mime": "audio/mpeg"
    }

app = FastAPI()

class Item(BaseModel):
    name: str
    value: str

data_store = []

@app.post("/add")
def add(item: Item):
    data_store.append(item)
    return item

@app.get("/db-all")
def all():
    return data_store

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





