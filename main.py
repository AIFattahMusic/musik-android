from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import requests
import os

app = FastAPI()

# ======================
# CONFIG
# ======================
SUNO_API_URL = "https://api.sunoapi.org/api/v1/generate/extend"
CALLBACK_URL = "https://musik-android.onrender.com/suno/callback"
SUNO_API_TOKEN = os.getenv("SUNO_API_TOKEN")


def get_headers():
    if not SUNO_API_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="SUNO_API_TOKEN belum diset di Render"
        )

    return {
        "Authorization": f"Bearer {SUNO_API_TOKEN}",
        "Content-Type": "application/json"
    }


# ======================
# IN-MEMORY STORE
# ======================
# NOTE: Untuk production → pindah ke DB
music_tasks = {}
"""
taskId: {
    status: PENDING / SUCCESS / FAILED
    audioUrl: str | None
    coverUrl: str | None
    duration: int | None
}
"""


# ======================
# SCHEMA
# ======================
class ExtendRequest(BaseModel):
    audioId: str
    continueAt: int = 60
    prompt: str | None = None
    title: str | None = None


# ======================
# HEALTH
# ======================
@app.get("/")
def health():
    return {
        "status": "ok",
        "token_loaded": bool(SUNO_API_TOKEN)
    }


# ======================
# EXTEND MUSIC
# ======================
@app.post("/suno/extend")
def extend_music(body: ExtendRequest):
    headers = get_headers()

    payload = {
        "defaultParamFlag": True,
        "audioId": body.audioId,
        "model": "V4_5ALL",
        "callBackUrl": CALLBACK_URL,
        "prompt": body.prompt or "Extend the music with more relaxing piano notes",
        "style": "Classical",
        "title": body.title or "Peaceful Piano Extended",
        "continueAt": body.continueAt,
        "styleWeight": 0.65,
        "audioWeight": 0.65,
        "weirdnessConstraint": 0.65,
        "negativeTags": "harsh, noisy, dissonant"
    }

    response = requests.post(
        SUNO_API_URL,
        json=payload,
        headers=headers,
        timeout=30
    )

    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code,
            detail=response.text
        )

    data = response.json()
    task_id = data.get("taskId")

    # simpan status awal
    music_tasks[task_id] = {
        "status": "PENDING",
        "audioUrl": None,
        "coverUrl": None,
        "duration": None
    }

    return {
        "success": True,
        "taskId": task_id,
        "status": "PENDING"
    }


# ======================
# CHECK STATUS
# ======================
@app.get("/suno/status/{task_id}")
def check_status(task_id: str):
    task = music_tasks.get(task_id)

    if not task:
        raise HTTPException(
            status_code=404,
            detail="Task ID tidak ditemukan"
        )

    return {
        "taskId": task_id,
        **task
    }


# ======================
# CALLBACK
# ======================
@app.post("/suno/callback")
async def suno_callback(request: Request):
    payload = await request.json()

    print("=== SUNO CALLBACK ===")
    print(payload)

    task_id = payload.get("taskId")
    status = payload.get("status")

    if task_id not in music_tasks:
        # callback terlambat / server restart
        music_tasks[task_id] = {}

    music_tasks[task_id].update({
        "status": status,
        "audioUrl": payload.get("audioUrl"),
        "coverUrl": payload.get("coverUrl"),
        "duration": payload.get("duration")
    })

    return {"status": "ok"}

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



