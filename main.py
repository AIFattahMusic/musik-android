import os
import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

# =========================
# APP
# =========================
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# CONFIG
# =========================
BASE_URL = os.getenv(
    "BASE_URL",
    "https://musik-android.onrender.com"
).rstrip("/")

SUNO_TOKEN = os.getenv("SUNO_TOKEN")
if not SUNO_TOKEN:
    raise RuntimeError("SUNO_TOKEN belum diset")

SUNO_GENERATE_URL = "https://api.sunoapi.org/api/v1/generate"
SUNO_RECORD_INFO_URL = "https://api.sunoapi.org/api/v1/generate/record-info"

HEADERS = {
    "Authorization": f"Bearer {SUNO_TOKEN}",
    "Content-Type": "application/json",
}

# =========================
# STORAGE
# =========================
GENERATED_DIR = "generated"
os.makedirs(GENERATED_DIR, exist_ok=True)

# =========================
# MODEL
# =========================
class GenerateRequest(BaseModel):
    prompt: str
    tags: str = ""
    custom_mode: bool = False
    instrumental: bool = False
    model: str = "V4_5"

# =========================
# HEALTH
# =========================
@app.get("/")
def root():
    return {"status": "ok"}

# =========================
# GENERATE MUSIC
# =========================
@app.post("/generate")
def generate_music(data: GenerateRequest):
    payload = {
        "prompt": data.prompt,
        "tags": data.tags,
        "custom_mode": data.custom_mode,
        "instrumental": data.instrumental,
        "model": data.model,
        "callbackUrl": f"{BASE_URL}/callback",
    }

    try:
        r = requests.post(
            SUNO_GENERATE_URL,
            headers=HEADERS,
            json=payload,
            timeout=60,
        )
    except requests.RequestException as e:
        raise HTTPException(502, str(e))

    if r.status_code != 200:
        raise HTTPException(r.status_code, r.text)

    return r.json()

# =========================
# CALLBACK (OPTIONAL)
# =========================
@app.post("/callback")
async def callback(req: Request):
    await req.json()
    return {"status": "received"}

# =========================
# STATUS (BENAR)
# =========================
@app.get("/generate/status/{task_id}")
def generate_status(task_id: str):
    mp3_path = f"{GENERATED_DIR}/{task_id}.mp3"

    # Jika file sudah ada
    if os.path.exists(mp3_path):
        return {
            "status": "done",
            "download_url": f"{BASE_URL}/generate/download/{task_id}",
        }

    try:
        r = requests.get(
            SUNO_RECORD_INFO_URL,
            headers=HEADERS,
            params={"taskId": task_id},
            timeout=30,
        )
    except requests.RequestException:
        return {"status": "processing"}

    if r.status_code != 200:
        return {"status": "processing"}

    res = r.json()
    data = res.get("data")
    if not data:
        return {"status": "processing"}

    status = data.get("status", "").upper()

    if status not in {"SUCCESS", "FIRST_SUCCESS", "TEXT_SUCCESS"}:
        return {
            "status": "processing",
            "raw_status": status,
        }

    audio_url = (
        data.get("response", {})
        .get("sunoData", {})
        .get("audioUrl")
    )

    if not audio_url:
        return {"status": "processing"}

    return {
        "status": "done",
        "download_url": f"{BASE_URL}/generate/download/{task_id}",
    }

# =========================
# DOWNLOAD (SMART & FINAL)
# =========================
@app.get("/generate/download/{task_id}")
def download_mp3(task_id: str):
    mp3_path = f"{GENERATED_DIR}/{task_id}.mp3"

    # 1. File sudah ada
    if os.path.exists(mp3_path):
        return FileResponse(
            mp3_path,
            media_type="audio/mpeg",
            filename=f"{task_id}.mp3",
        )

    # 2. Ambil info dari Suno (BENAR)
    try:
        r = requests.get(
            SUNO_RECORD_INFO_URL,
            headers=HEADERS,
            params={"taskId": task_id},
            timeout=30,
        )
    except requests.RequestException:
        return JSONResponse(
            status_code=202,
            content={"status": "processing"},
        )

    if r.status_code != 200:
        return JSONResponse(
            status_code=202,
            content={"status": "processing"},
        )

    res = r.json()
    data = res.get("data")
    if not data:
        return JSONResponse(
            status_code=202,
            content={"status": "processing"},
        )

    status = data.get("status", "").upper()
    if status not in {"SUCCESS", "FIRST_SUCCESS", "TEXT_SUCCESS"}:
        return JSONResponse(
            status_code=202,
            content={"status": "processing", "raw_status": status},
        )

    audio_url = (
        data.get("response", {})
        .get("sunoData", {})
        .get("audioUrl")
    )

    if not audio_url:
        return JSONResponse(
            status_code=202,
            content={"status": "processing"},
        )

    # 3. Download MP3
    audio_resp = requests.get(audio_url, timeout=60)
    if audio_resp.status_code != 200:
        raise HTTPException(500, "Gagal download audio")

    with open(mp3_path, "wb") as f:
        f.write(audio_resp.content)

    return FileResponse(
        mp3_path,
        media_type="audio/mpeg",
        filename=f"{task_id}.mp3",
    )
