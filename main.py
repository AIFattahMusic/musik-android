import os
import uuid
import requests
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from supabase import create_client

# ================= ENV =================

SUNO_API_KEY = os.getenv("SUNO_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUNO_API_KEY:
    raise Exception("SUNO_API_KEY missing")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("SUPABASE ENV missing")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

SUNO_BASE_API = "https://api.kie.ai/api/v1"
MUSIC_GENERATE_URL = f"{SUNO_BASE_API}/generate"
STATUS_URL = f"{SUNO_BASE_API}/generate/record-info"

# ================= APP =================

app = FastAPI(title="AI Music API", version="2.0")

# ================= MODELS =================

class GenerateMusicRequest(BaseModel):
    prompt: str
    style: Optional[str] = None
    title: Optional[str] = None
    instrumental: bool = False
    customMode: bool = False
    model: str = "V4_5"

# ================= HELPERS =================

def suno_headers():
    return {
        "Authorization": f"Bearer {SUNO_API_KEY}",
        "Content-Type": "application/json"
    }

# ================= ROUTES =================

@app.get("/")
def root():
    return {"status": "running"}

@app.post("/generate-music")
async def generate_music(payload: GenerateMusicRequest):

    body = {
        "prompt": payload.prompt,
        "customMode": payload.customMode,
        "instrumental": payload.instrumental,
        "model": payload.model
    }

    if payload.style:
        body["style"] = payload.style
    if payload.title:
        body["title"] = payload.title

    async with httpx.AsyncClient(timeout=60) as client:
        res = await client.post(
            MUSIC_GENERATE_URL,
            headers=suno_headers(),
            json=body
        )

    if res.status_code != 200:
        raise HTTPException(status_code=500, detail=res.text)

    return res.json()


@app.get("/record-info/{task_id}")
async def record_info(task_id: str):
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.get(
                STATUS_URL,
                headers=suno_headers(),
                params={"taskId": task_id}
            )

        data = res.json()

        suno_data = data["data"]["response"]["sunoData"][0]

        audio_url = suno_data.get("audioUrl")
        title = suno_data.get("title", "Untitled")
        lyrics = suno_data.get("prompt", "")
        artist = "AI Generator"
        genre = "AI"

        if audio_url:
            file_id = str(uuid.uuid4())
            audio_path = f"songs/{file_id}.mp3"

            # download mp3 dari Suno
            audio_bytes = requests.get(audio_url).content

            # upload ke Supabase
            supabase.storage.from_("music").upload(
                audio_path,
                audio_bytes,
                {"upsert": True}
            )

            # simpan ke database
            supabase.table("songs").insert({
                "title": title,
                "artist": artist,
                "genre": genre,
                "lyrics": lyrics,
                "audio_path": audio_path,
                "cover_path": None
            }).execute()

            print("UPLOAD SUCCESS")

        return data

    except Exception as e:
        print("ERROR:", e)
        return {"error": str(e)}
