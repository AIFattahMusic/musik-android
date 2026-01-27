from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse
import os
import requests
import threading
import sqlite3

app = FastAPI()

# =====================
# CONFIG
# =====================
SAVE_DIR = "generated_music"
os.makedirs(SAVE_DIR, exist_ok=True)

SUNO_API_KEY = os.environ.get("SUNO_API_KEY")
SUNO_URL = "https://api.sunoapi.org/api/v1/generate"
CALLBACK_URL = "https://musik-android.onrender.com/generate-music-callback"

DB_PATH = "music.db"

# =====================
# DATABASE
# =====================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS songs ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "task_id TEXT UNIQUE, "
        "status TEXT, "
        "filename TEXT)"
    )
    conn.commit()
    conn.close()

init_db()

# =====================
# ROOT
# =====================
@app.get("/")
def root():
    return {"status": "ok"}

# =====================
# GENERATE
# =====================
@app.post("/generate")
def generate():
    if not SUNO_API_KEY:
        raise HTTPException(500, "SUNO_API_KEY belum diset")

    payload = {
        "prompt": "chill lo-fi instrumental",
        "make_instrumental": True,
        "callback_url": CALLBACK_URL
    }

    headers = {
        "Authorization": f"Bearer {SUNO_API_KEY}",
        "Content-Type": "application/json"
    }

    r = requests.post(SUNO_URL, json=payload, headers=headers)
    data = r.json()

    task_id = data.get("data", {}).get("task_id")
    if not task_id:
        raise HTTPException(500, "Generate gagal")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO songs (task_id, status, filename) VALUES (?, ?, ?)",
        (task_id, "pending", "")
    )
    conn.commit()
    conn.close()

    return {"task_id": task_id}

# =====================
# DOWNLOAD (BACKGROUND)
# =====================
def download_audio(task_id, musics):
    for music in musics:
        audio_url = music.get("audio_url")
        if not audio_url:
            continue

        r = requests.get(audio_url)
        if r.status_code == 200:
            filename = task_id + ".mp3"
            path = os.path.join(SAVE_DIR, filename)

            with open(path, "wb") as f:
                f.write(r.content)

            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute(
                "UPDATE songs SET status=?, filename=? WHERE task_id=?",
                ("completed", filename, task_id)
            )
            conn.commit()
            conn.close()

# =====================
# CALLBACK
# =====================
@app.post("/generate-music-callback")
async def callback(request: Request):
    payload = await request.json()

    if payload.get("code") == 200:
        data = payload.get("data", {})
        if data.get("callbackType") == "complete":
            threading.Thread(
                target=download_audio,
                args=(data.get("task_id"), data.get("data", [])),
                daemon=True
            ).start()

    return JSONResponse({"status": "ok"})

# =====================
# PLAY
# =====================
@app.get("/play/{task_id}")
def play(task_id: str):
    path = os.path.join(SAVE_DIR, task_id + ".mp3")
    if not os.path.exists(path):
        raise HTTPException(404, "Belum siap")

    return FileResponse(path, media_type="audio/mpeg")

# =====================
# DOWNLOAD
# =====================
@app.get("/download/{task_id}")
def download(task_id: str):
    path = os.path.join(SAVE_DIR, task_id + ".mp3")
    if not os.path.exists(path):
        raise HTTPException(404, "Belum siap")

    return FileResponse(path, filename=task_id + ".mp3")
