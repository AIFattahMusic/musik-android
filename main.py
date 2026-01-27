from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker
import os
import threading
import requests

# ======================
# APP
# ======================
app = FastAPI()

# ======================
# CONFIG
# ======================
SAVE_DIR = "generated_music"
os.makedirs(SAVE_DIR, exist_ok=True)

SUNO_API_KEY = os.environ.get("SUNO_API_KEY")
SUNO_URL = "https://api.sunoapi.org/api/v1/generate"
CALLBACK_URL = "https://musik-android.onrender.com/generate-music-callback"

# ======================
# DATABASE (SQLite)
# ======================
DATABASE_URL = "sqlite:///./music.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Song(Base):
    __tablename__ = "songs"

    id = Column(Integer, primary_key=True)
    task_id = Column(String, unique=True, index=True)
    status = Column(String)
    filename = Column(String)


Base.metadata.create_all(bind=engine)

# ======================
# ROOT (CEK HIDUP)
# ======================
@app.get("/")
def root():
    return {"status": "ok"}

# ======================
# 1️⃣ GENERATE 1 LAGU
# ======================
@app.post("/generate")
def generate_song():
    if not SUNO_API_KEY:
        raise HTTPException(500, "SUNO_API_KEY belum diset")

    payload = {
        "prompt": "chill lo-fi instrumental, relaxing vibe",
        "make_instrumental": True,
        "callback_url": CALLBACK_URL
    }

    headers = {
        "Authorization": f"Bearer {SUNO_API_KEY}",
        "Content-Type": "application/json"
    }

    r = requests.post(SUNO_URL, json=payload, headers=headers, timeout=30)
    data = r.json()

    task_id = data.get("data", {}).get("task_id")
    if not task_id:
        raise HTTPException(500, "Generate gagal")

    db = SessionLocal()
    db.add(Song(task_id=task_id, status="pending", filename=""))
    db.commit()
    db.close()

    return {"task_id": task_id, "status": "pending"}

# ======================
# 2️⃣ CALLBACK SUNO
# ======================
def download_music(task_id, musics):
    db = SessionLocal()
    song = db.query(Song).filter(Song.task_id == task_id).first()

    if not song:
        db.close()
        return

    for music in musics:
        audio_url = music.get("audio_url")
        if not audio_url:
            continue

        r = requests.get(audio_url, timeout=30)
        if r.status_code == 200:
            filename = f"{task_id}.mp3"
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
