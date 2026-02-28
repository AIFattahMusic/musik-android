import os
import httpx
import requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import logging

# Konfigurasi logging untuk melihat output di log server
logging.basicConfig(level=logging.INFO)

# ==================================================
# FOLDER MEDIA
# Membuat direktori 'media' jika belum ada untuk menyimpan file MP3
# ==================================================
os.makedirs("media", exist_ok=True)

# ==================================================
# KONFIGURASI & VARIABEL GLOBAL
# ==================================================
# Kunci API untuk layanan Suno AI, diambil dari environment variable
SUNO_API_KEY = os.getenv("SUNO_API_KEY")

# URL dasar server Anda. Penting untuk callback dan link file.
# Default ke URL OnRender jika tidak diatur.
BASE_URL = os.getenv(
    "BASE_URL",
    "https://musik-android.onrender.com"
)

# URL yang akan dipanggil oleh Suno API setelah selesai memproses lagu
CALLBACK_URL = f"{BASE_URL}/callback"

# Endpoint dari API eksternal (Suno via proxy Kie.ai)
SUNO_BASE_API = "https://api.kie.ai/api/v1"
STYLE_GENERATE_URL = f"{SUNO_BASE_API}/style/generate"
MUSIC_GENERATE_URL = f"{SUNO_BASE_API}/generate"
STATUS_URL = f"{SUNO_BASE_API}/generate/record-info"

# ==================================================
# INISIALISASI APLIKASI FASTAPI
# ==================================================
app = FastAPI(
    title="AI Music Suno API Wrapper",
    version="3.0.0",
    description="Server proxy untuk menjembatani aplikasi Android dengan Suno API."
)

# Membuat endpoint statis agar file di folder 'media' bisa diakses dari web
# Contoh: https://musik-android.onrender.com/media/namafile.mp3
app.mount("/media", StaticFiles(directory="media"), name="media")

# ==================================================
# MODEL DATA (PYDANTIC)
# Mendefinisikan struktur data untuk request dari aplikasi Android
# ==================================================
class BoostStyleRequest(BaseModel):
    content: str

class GenerateMusicRequest(BaseModel):
    prompt: str
    style: Optional[str] = None
    title: Optional[str] = None
    instrumental: bool = False
    customMode: bool = False
    model: str = "V4_5"

# ==================================================
# FUNGSI HELPERS
# ==================================================
def suno_headers():
    """Membuat header otorisasi untuk setiap request ke Suno API."""
    if not SUNO_API_KEY:
        # Jika API Key tidak ada, server akan error. Ini penting.
        raise HTTPException(status_code=500, detail="SUNO_API_KEY belum diatur di server!")
    return {
        "Authorization": f"Bearer {SUNO_API_KEY}",
        "Content-Type": "application/json"
    }

# ==================================================
# ENDPOINTS DASAR
# ==================================================
@app.get("/")
def root():
    """Endpoint utama untuk memeriksa apakah server berjalan."""
    return {"status": "running", "version": "3.0.0"}

@app.get("/health")
def health():
    """Endpoint untuk monitoring kesehatan server."""
    return {"status": "ok"}

# ==================================================
# ENDPOINT GENERATE MUSIC
# ==================================================
@app.post("/generate-music")
async def generate_music(payload: GenerateMusicRequest):
    """
    Endpoint yang dipanggil aplikasi Android untuk mulai membuat lagu.
    Meneruskan request ke Suno API dan menambahkan callBackUrl.
    """
    logging.info(f"Menerima request generate music: {payload.prompt}")
    
    body = {
        "prompt": payload.prompt,
        "customMode": payload.customMode,
        "instrumental": payload.instrumental,
        "model": payload.model,
        "callBackUrl": CALLBACK_URL  # Memberitahu Suno ke mana harus mengirim notifikasi
    }

    if payload.style:
        body["style"] = payload.style
    if payload.title:
        body["title"] = payload.title

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            res = await client.post(
                MUSIC_GENERATE_URL,
                headers=suno_headers(),
                json=body
            )
            res.raise_for_status()  # Error jika status code bukan 2xx
            logging.info("Request ke Suno API berhasil dikirim.")
            return res.json()
        except httpx.HTTPStatusError as e:
            logging.error(f"Error saat request ke Suno API: {e.response.text}")
            raise HTTPException(status_code=e.response.status_code, detail=f"Gagal menghubungi Suno API: {e.response.text}")
        except Exception as e:
            logging.error(f"Terjadi error tidak terduga: {e}")
            raise HTTPException(status_code=500, detail="Terjadi error internal pada server.")


# ==================================================
# ENDPOINT POLLING (PENGAMBILAN LAGU)
# Inilah yang dipanggil berulang-ulang oleh aplikasi untuk cek status
# ==================================================
@app.get("/generate/status/{task_id}")
def generate_status(task_id: str):
    """
    Endpoint yang dipanggil aplikasi untuk memeriksa status pembuatan lagu.
    Jika sudah selesai, endpoint ini akan men-download lagu dari URL sementara
    dan menyediakannya melalui URL permanen di server ini.
    """
    logging.info(f"Mengecek status untuk task_id: {task_id}")
    
    try:
        r = requests.get(
            STATUS_URL,
            headers=suno_headers(),
            params={"taskId": task_id},
            timeout=30
        )
        r.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"Gagal mengambil status dari Suno untuk task {task_id}: {e}")
        return {"status": "processing", "detail": "Gagal menghubungi Suno, mencoba lagi..."}

    res = r.json()
    item = res.get("data")

    # Jika data adalah list, ambil item pertama
    if isinstance(item, list) and len(item) > 0:
        item = item[0]

    if not item:
        logging.warning(f"Data kosong dari Suno untuk task {task_id}.")
        return {"status": "processing", "detail": "Menunggu data dari Suno..."}

    state = item.get("state") or item.get("status")

    # Selama statusnya belum 'succeeded', kembalikan 'processing'
    if state != "succeeded":
        logging.info(f"Task {task_id} masih dalam status: {state}")
        return {"status": "processing", "detail": f"Status saat ini: {state}"}

    # Jika sudah 'succeeded', ambil URL streaming sementara
    stream_url = item.get("streamAudioUrl")
    if not stream_url:
        logging.error(f"Task {task_id} berhasil tapi tidak ada streamAudioUrl.")
        return {"status": "processing", "detail": "Lagu selesai tapi URL tidak ditemukan, mencoba lagi..."}

    # Path untuk menyimpan file mp3 di server
    file_path = f"media/{task_id}.mp3"
    public_audio_url = f"{BASE_URL}/{file_path}"

    # Jika file belum ada di server, download dari URL sementara
    if not os.path.exists(file_path):
        try:
            logging.info(f"Mendownload lagu untuk task {task_id} dari {stream_url}")
            audio_bytes = requests.get(stream_url, timeout=60).content
            with open(file_path, "wb") as f:
                f.write(audio_bytes)
            logging.info(f"Lagu untuk task {task_id} berhasil disimpan di {file_path}")
        except requests.RequestException as e:
            logging.error(f"Gagal mendownload audio dari stream URL untuk task {task_id}: {e}")
            raise HTTPException(status_code=500, detail="Gagal mendownload file audio dari Suno.")

    # Kembalikan status "done" dengan URL publik yang bisa diakses aplikasi
    return {
        "status": "done",
        "audio_url": public_audio_url
    }

# ==================================================
# ENDPOINT CALLBACK
# ==================================================
@app.post("/callback")
async def callback(request: Request):
    """Endpoint ini dipanggil oleh Suno API saat ada update status.
    Untuk saat ini, kita hanya mencatat datanya."""
    try:
        data = await request.json()
        logging.info(f"CALLBACK DITERIMA: {data}")
        return {"ok": True}
    except Exception as e:
        logging.error(f"Error pada callback: {e}")
        return {"ok": False}
