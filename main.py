from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse
import os
import threading
import requests

app = FastAPI()

SAVE_DIR = "generated_music"
os.makedirs(SAVE_DIR, exist_ok=True)

SUNO_API_URL = "https://api.sunoapi.org/api/v1/generate"  # contoh
SUNO_API_KEY = os.environ.get("SUNO_API_KEY")


# =========================
# 1️⃣ GENERATE 1 LAGU
# =========================
@app.post("/generate")
def generate_one_song():
    payload = {
        "prompt": "chill lo-fi instrumental",
        "n_tokens": 1,
        "callback_url": "https://musik-android.onrender.com/generate-music-callback"
    }

    headers = {
        "Authorization": f"Bearer {SUNO_API_KEY}",
        "Content-Type": "application/json"
    }

    r = requests.post(SUNO_API_URL, json=payload, headers=headers, timeout=30)

    return r.json()


# =========================
# 2️⃣ CALLBACK SUNO
# =========================
def download_music(task_id, musics):
    for i, music in enumerate(musics, start=1):
        audio_url = music.get("audio_url")
        if not audio_url:
            continue

        r = requests.get(audio_url, timeout=30)
        if r.status_code == 200:
            filename = f"{task_id}.mp3"
            with open(os.path.join(SAVE_DIR, filename), "wb") as f:
                f.write(r.content)
            print("Saved:", filename)


@app.post("/generate-music-callback")
async def generate_music_callback(request: Request):
    payload = await request.json()

    code = payload.get("code")
    data = payload.get("data", {})
    callback_type = data.get("callbackType")
    task_id = data.get("task_id")
    musics = data.get("data", [])

    # BALAS CEPAT KE SUNO
    response = JSONResponse({"status": "received"}, status_code=200)

    if code == 200 and callback_type == "complete":
        threading.Thread(
            target=download_music,
            args=(task_id, musics),
            daemon=True
        ).start()

    return response


# =========================
# 3️⃣ PUTAR LAGU
# =========================
@app.get("/play/{filename}")
def play_music(filename: str):
    filepath = os.path.join(SAVE_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        filepath,
        media_type="audio/mpeg",
        filename=filename
    )


# =========================
# 4️⃣ DOWNLOAD LAGU
# =========================
@app.get("/download/{filename}")
def download_music_file(filename: str):
    filepath = os.path.join(SAVE_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        filepath,
        media_type="audio/mpeg",
        filename=filename,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
