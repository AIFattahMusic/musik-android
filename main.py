import os
import requests
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel

app = FastAPI()

SUNO_TOKEN = os.getenv("SUNO_TOKEN")
SUNO_API_URL = "https://api.sunoapi.org/api/v1/generate"
BASE_URL = "https://musik-android.onrender.com"

HEADERS = {
    "Authorization": f"Bearer {SUNO_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

DB = []  # simpan hasil callback di memory


class GenerateRequest(BaseModel):
    prompt: str
    tags: str | None = None


@app.get("/")
def root():
    return {"status": "ok"}


# ======================
# GENERATE MUSIC
# ======================
@app.post("/generate/full-song")
def generate_song(data: GenerateRequest):
    payload = {
        "prompt": data.prompt,
        "tags": data.tags or "",
        "model": "chirp-v3-5",              # ✅ MODEL RESMI
        "callBackUrl": f"{BASE_URL}/callback"
    }

    r = requests.post(
        SUNO_API_URL,
        headers=HEADERS,
        json=payload,
        timeout=60
    )

    if r.status_code != 200:
        raise HTTPException(r.status_code, r.text)

    return r.json()


# ======================
# CALLBACK SUNO
# ======================
@app.post("/callback")
async def callback(request: Request):
    body = await request.json()

    if body.get("code") == 200 and body["data"]["callbackType"] == "complete":
        for item in body["data"]["data"]:
            DB.append({
                "title": item["title"],
                "audio_url": item["audio_url"],
                "image_url": item["image_url"],
                "duration": item["duration"],
            })

    return {"ok": True}


# ======================
# LIHAT HASIL / DOWNLOAD
# ======================
@app.get("/songs")
def songs():
    return DB

