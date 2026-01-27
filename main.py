from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse
import os
import threading
import requests
import sqlite3

app = FastAPI()

# ======================================================
# CONFIG
# ======================================================
SAVE_DIR = "generated_music"
os.makedirs(SAVE_DIR, exist_ok=True)

SUNO_API_KEY = os.environ.get("SUNO_API_KEY")
SUNO_GENERATE_URL = "https://api.sunoapi.org/api/v1/generate"
CALLBACK_URL = "https://musik-android.onrender.com/generate-music-callback"

DB_PATH = "music.db"

# ======================================================
# DATABASE (sqlite3 – TANPA SQLALCHEMY)
# ======================================================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT UNIQUE,
            status TEXT,
            title TEXT,
            prompt TEXT,
            audio_url TEXT,
            filename TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ======================================================
# ROOT
# ======================================================
@app.get("/")
def root():
    return {"status": "ok"}

# ======================================================
# GENERATE 1 MUSIC (REQUEST KE SUNO)
# ======================================================
@app.post("/generate")
def generate_music():
    if not SUNO_API_KEY:
        raise HTTPException(500, "SUNO_API_KEY belum diset")

    prompt = "chill lo-fi instrumental, relaxing vibe"

    payload = {
        "prompt": prompt,
        "make_instrumental": True,
        "callback_url": CALLBACK_URL
    }

    headers = {
        "Authorization": f"Bearer {SUNO_API_KEY}",
        "Content-Type": "application/json"
    }

    r = requests.post(
        SUNO_GENERATE_URL,
        json=payload,
        headers=headers,
        timeout=30
    )

    result = r.json()
    task_id = result.get("data", {}).get("task_id")

    if not task_id:
        raise HTTPException(500, "Generate gagal")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO songs (task_id, status, prompt) VALUES (?, ?, ?)",
        (task_id, "pending", prompt)
    )
    conn.commit()
    conn.close()

    return {
        "task_id": task_id,
        "status": "pending",
        "message": "Music generation started"
    }

# ======================================================
# DOWNLOAD AUDIO (BACKGROUND)
# ======================================================
def download_audio(task_id: str, musics: list):
    for music in musics:
        audio_url = music.get("audio_url")
        title = music.get("title")

        if not audio_url:
            continue

        try:
            r = requests.get(audio_url, timeout=30)
            if r.status_code == 200:
                filename = f"{task_id}.mp3"
                filepath = os.path.join(SAVE_DIR, filename)

                with open(filepath, "wb") as f:
                    f.write(r.content)

                conn = sqlite3.connect(DB_PATH)
                cur = conn.cursor()
                cur.execute(
                    """
                    UPDATE songs
                    SET status=?, title=?, audio_url=?, filename=?
                    WHERE task_id=?
                    """,
                    ("completed", title, audio_url, filename, task_id)
                )
                conn.commit()
                conn.close()
        except Exception:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute(
                "UPDATE songs SET status=? WHERE task_id=?",
                ("failed", task_id)
            )
            conn.commit()
            conn.close()

# ======================================================
# CALLBACK DARI SUNO (SESUAI DOCS)
# ======================================================
@app.post("/generate-music-callback")
async def generate_music_callback(request: Request):
    payload = await request.json()

    # WAJIB BALAS CEPAT
    response = JSONResponse({"status": "received"}, status_code=200)

    code = payload.get("code")
    data = payload.get("data", {})

    callback_type = data.get("callbackType")
    task_id = data.get("task_id")
    musics = data.get("data", [])

    # HANYA DOWNLOAD SAAT COMPLETE
    if code == 200 and callback_type == "complete":
        threading.Thread(
            target=download_audio,
            args=(task_id, musics),
            daemon=True
        ).start()

    return response

# ======================================================
# LIST SONGS (DATABASE)
# ======================================================
@app.get("/songs")
def list_songs():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT task_id, status, title, filename FROM songs")
    rows = cur.fetchall()
    conn.close()

    return [
        {
            "task_id": r[0],
            "status": r[1],
            "title": r[2],
            "filename": r[3]
        }
        for r in rows
    ]

# ======================================================
# PLAY MUSIC
# ======================================================
@app.get("/play/{task_id}")
def play_music(task_id: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT filename FROM songs WHERE task_id=?", (task_id,))
    row = cur.fetchone()
    conn.close()

    if not row or not row[0]:
        raise HTTPException(404, "Music not ready")

    return FileResponse(
        os.path.join(SAVE_DIR, row[0]),
        media_type="audio/mpeg"
    )

# ======================================================
# DOWNLOAD MUSIC
# ======================================================
@app.get("/download/{task_id}")
def download_music(task_id: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT filename FROM songs WHERE task_id=?", (task_id,))
    row = cur.fetchone()
    conn.close()

    if not row or not row[0]:
        raise HTTPException(404, "Music not ready")

    return FileResponse(
        os.path.join(SAVE_DIR, row[0]),
        media_type="audio/mpeg",
        filename=row[0]
    )            filename = f"{task_id}.mp3"
            path = os.path.join(SAVE_DIR, filename)

            with open(path, "wb") as f:
                f.write(r.content)

            song.status = "completed"
            song.filename = filename
            db.commit()

    db.close()


@app.post("/generate-music-callback")
async def generate_music_callback(request: Request):
    payload = await request.json()

    if payload.get("code") == 200:
        data = payload.get("data", {})
        if data.get("callbackType") == "complete":
            threading.Thread(
                target=download_music,
                args=(data.get("task_id"), data.get("data", [])),
                daemon=True
            ).start()

    return JSONResponse({"status": "received"}, status_code=200)

# ======================
# 3️⃣ LIST LAGU (DATABASE)
# ======================
@app.get("/songs")
def list_songs():
    db = SessionLocal()
    songs = db.query(Song).all()
    db.close()

    return [
        {
            "task_id": s.task_id,
            "status": s.status,
            "filename": s.filename
        }
        for s in songs
    ]

# ======================
# 4️⃣ PUTAR LAGU
# ======================
@app.get("/play/{task_id}")
def play_song(task_id: str):
    db = SessionLocal()
    song = db.query(Song).filter(Song.task_id == task_id).first()
    db.close()

    if not song or not song.filename:
        raise HTTPException(404, "Song not ready")

    return FileResponse(
        os.path.join(SAVE_DIR, song.filename),
        media_type="audio/mpeg"
    )

# ======================
# 5️⃣ DOWNLOAD LAGU
# ======================
@app.get("/download/{task_id}")
def download_song(task_id: str):
    db = SessionLocal()
    song = db.query(Song).filter(Song.task_id == task_id).first()
    db.close()

    if not song or not song.filename:
        raise HTTPException(404, "Song not ready")

    return FileResponse(
        os.path.join(SAVE_DIR, song.filename),
        media_type="audio/mpeg",
        filename=song.filename
    )

