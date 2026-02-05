import os
import httpx
import requests
import psycopg2

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

# ==================================================
# PASTIKAN FOLDER MEDIA ADA
# ==================================================
os.makedirs("media", exist_ok=True)

# ================= ENV =================
SUNO_API_KEY = os.getenv("SUNO_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

BASE_URL = os.getenv(
    "BASE_URL",
    "https://musik-android.onrender.com"
)

CALLBACK_URL = f"{BASE_URL}/callback"

SUNO_BASE_API = "https://api.kie.ai/api/v1"
STYLE_GENERATE_URL = f"{SUNO_BASE_API}/style/generate"
MUSIC_GENERATE_URL = f"{SUNO_BASE_API}/generate"
STATUS_URL = f"{SUNO_BASE_API}/generate/record-info"

# ================= APP =================
app = FastAPI(
    title="AI Music Suno API Wrapper",
    version="1.0.3"
)

# ================= STATIC =================
app.mount("/media", StaticFiles(directory="media"), name="media")

# ================= REQUEST MODELS =================
class BoostStyleRequest(BaseModel):
    content: str


class GenerateMusicRequest(BaseModel):
    prompt: str
    style: Optional[str] = None
    title: Optional[str] = None
    instrumental: bool = False
    vocalGender: Optional[str] = None  # "m" | "f"
    lyrics: Optional[str] = None
    customMode: bool = True
    model: str = "V4_5"


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


def get_conn():
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL not set")
    return psycopg2.connect(DATABASE_URL)


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

    if payload.vocalGender:
        body["vocalGender"] = payload.vocalGender

    if payload.lyrics:
        body["lyrics"] = payload.lyrics

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
        res = await client.get(
            STATUS_URL,
            headers=suno_headers(),
import os
import httpx
import requests
import psycopg2

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

# ==================================================
# PASTIKAN FOLDER MEDIA ADA
# ==================================================
os.makedirs("media", exist_ok=True)

# ================= ENV =================
SUNO_API_KEY = os.getenv("SUNO_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

BASE_URL = os.getenv(
    "BASE_URL",
    "https://musik-android.onrender.com"
)

CALLBACK_URL = f"{BASE_URL}/callback"

SUNO_BASE_API = "https://api.kie.ai/api/v1"
STYLE_GENERATE_URL = f"{SUNO_BASE_API}/style/generate"
MUSIC_GENERATE_URL = f"{SUNO_BASE_API}/generate"
STATUS_URL = f"{SUNO_BASE_API}/generate/record-info"

# ================= APP =================
app = FastAPI(
    title="AI Music Suno API Wrapper",
    version="1.0.4"
)

# ================= STATIC =================
app.mount("/media", StaticFiles(directory="media"), name="media")

# ================= REQUEST MODELS =================
class BoostStyleRequest(BaseModel):
    content: str


class GenerateMusicRequest(BaseModel):
    prompt: Optional[str] = None      # bisa kosong
    lyrics: Optional[str] = None      # lirik mentah dari APK (multi-line)
    style: Optional[str] = None
    title: Optional[str] = None
    instrumental: bool = False
    vocalGender: Optional[str] = None
    customMode: bool = True
    model: str = "V4_5"


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


def get_conn():
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL not set")
    return psycopg2.connect(DATABASE_URL)


def clean_text(text: str) -> str:
    """
    Membersihkan teks dari karakter bermasalah
    agar aman dikirim sebagai JSON & prompt
    """
    if not text:
        return ""

    return (
        text
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .strip()
    )


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
    # ==================================================
    # 🔑 LOGIC INTI: LIRIK FULL MASUK KE PROMPT
    # ==================================================
    final_prompt = ""

    if payload.lyrics:
        final_prompt = clean_text(payload.lyrics)
    elif payload.prompt:
        final_prompt = clean_text(payload.prompt)
    else:
        raise HTTPException(status_code=422, detail="prompt or lyrics is required")

    body = {
        "prompt": final_prompt,
        "customMode": payload.customMode,
        "instrumental": payload.instrumental,
        "model": normalize_model(payload.model),
        "callBackUrl": CALLBACK_URL
    }

    if payload.style:
        body["style"] = payload.style

    if payload.title:
        body["title"] = payload.title

    if payload.vocalGender:
        body["vocalGender"] = payload.vocalGender

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
        res = await client.get(
            STATUS_URL,
            headers=suno_headers(),
            params={"taskId": task_id}
        )
    return res.json()


@app.post("/callback")
async def callback(request: Request):
    data = await request.json()

    try:
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

        image_url = item.get("imageUrl")
        lyrics = item.get("prompt")  # lirik final dari prompt
        title = item.get("title", "Untitled")

        # ===== SAVE AUDIO =====
        audio_bytes = requests.get(audio_url).content
        file_path = f"media/{task_id}.mp3"

        with open(file_path, "wb") as f:
            f.write(audio_bytes)

        local_audio_url = f"{BASE_URL}/media/{task_id}.mp3"

        # ===== SAVE DB =====
        conn = get_conn()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO songs (task_id, title, audio_url, cover_url, lyrics, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (task_id) DO NOTHING
            """,
            (
                task_id,
                title,
                local_audio_url,
                image_url,
                lyrics,
                "done"
            )
        )

        conn.commit()
        cur.close()
        conn.close()

        return {"status": "saved"}

    except Exception as e:
        return {"status": "error", "error": str(e)}


# ================= DB TEST =================
@app.get("/db-all")
def db_all():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public';
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows
