from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import requests
import os

app = FastAPI(title="Suno Extend API")

# ======================
# CONFIG
# ======================
SUNO_API_URL = "https://api.sunoapi.org/api/v1/generate/extend"
SUNO_API_TOKEN = os.getenv("SUNO_API_TOKEN")

if not SUNO_API_TOKEN:
    raise RuntimeError("SUNO_API_TOKEN belum diset di environment")

CALLBACK_URL = "https://musik-android.onrender.com/suno/callback"

HEADERS = {
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
        "service": "Suno Extend API"
    }


# ======================
# EXTEND MUSIC
# ======================
@app.post("/suno/extend")
def extend_music(body: ExtendRequest):
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
        res = requests.post(
            SUNO_API_URL,
            json=payload,
            headers=HEADERS,
            timeout=30
        )
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=str(e))

    if res.status_code != 200:
        raise HTTPException(
            status_code=res.status_code,
            detail=res.text
        )

    return {
        "success": True,
        "result": res.json()
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
    Biasanya:
    {
      taskId,
      status: SUCCESS | FAILED,
      audioUrl,
      coverUrl,
      duration
    }
    """

    # TODO (opsional):
    # - simpan ke database
    # - update status user
    # - download audio

    return {"status": "ok"}
