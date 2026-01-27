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
            detail="SUNO_API_TOKEN belum diset di Render Environment"
        )

    return {
        "Authorization": f"Bearer {SUNO_API_TOKEN}",
        "Content-Type": "application/json"
    }


# ======================
# SCHEMA
# ======================
class ExtendRequest(BaseModel):
    audioId: str
    continueAt: int = 60
    prompt: str | None = None
    title: str | None = None


# ======================
# HEALTH CHECK
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

    try:
        response = requests.post(
            SUNO_API_URL,
            json=payload,
            headers=headers,
            timeout=30
        )
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=str(e))

    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code,
            detail=response.text
        )

    return {
        "success": True,
        "data": response.json()
    }


# ======================
# SUNO CALLBACK
# ======================
@app.post("/suno/callback")
async def suno_callback(request: Request):
    payload = await request.json()

    print("=== SUNO CALLBACK RECEIVED ===")
    print(payload)

    """
    Contoh isi:
    - taskId
    - status: SUCCESS / FAILED
    - audioUrl
    - coverUrl
    - duration
    """

    # TODO:
    # simpan ke database / kirim ke client / download audio

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


