import os
import uuid
import asyncio
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
    raise Exception("SUPABASE env missing")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

SUNO_BASE_API = "https://api.kie.ai/api/v1"
GENERATE_URL = f"{SUNO_BASE_API}/generate"
STATUS_URL = f"{SUNO_BASE_API}/generate/record-info"

app = FastAPI(title="AI Music Auto Save", version="4.0")

# ================= MODEL =================

class GenerateMusicRequest(BaseModel):
    prompt: str
    style: Optional[str] = None
    title: Optional[str] = None
    instrumental: bool = False
    customMode: bool = False
    model: str = "V4_5"

def suno_headers():
    return {
        "Authorization": f"Bearer {SUNO_API_KEY}",
        "Content-Type": "application/json"
    }

# ================= AUTO GENERATE + SAVE =================

@app.post("/generate-music-auto")
async def generate_music_auto(payload: GenerateMusicRequest):

    # 1️⃣ Generate task
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
        gen_res = await client.post(
            GENERATE_URL,
            headers=suno_headers(),
            json=body
        )

    if gen_res.status_code != 200:
        raise HTTPException(status_code=500, detail=gen_res.text)

    gen_data = gen_res.json()
    task_id = gen_data["data"]["taskId"]

    # 2️⃣ Polling sampai selesai
    for _ in range(30):  # max 30x polling
        await asyncio.sleep(5)

        async with httpx.AsyncClient(timeout=30) as client:
            status_res = await client.get(
                STATUS_URL,
                headers=suno_headers(),
                params={"taskId": task_id}
            )

        status_data = status_res.json()

        try:
            suno_data = status_data["data"]["response"]["sunoData"][0]
            audio_url = suno_data.get("audioUrl")
            state = suno_data.get("state")

            if state == "succeeded" and audio_url:
                # 3️⃣ Download
                audio_bytes = requests.get(audio_url).content

                file_id = str(uuid.uuid4())
                audio_path = f"songs/{file_id}.mp3"

                # 4️⃣ Upload ke Supabase
                supabase.storage.from_("music").upload(
                    audio_path,
                    audio_bytes,
                    {"upsert": True}
                )

                # 5️⃣ Insert DB
                supabase.table("songs").insert({
                    "title": suno_data.get("title", "Untitled"),
                    "artist": "AI Generator",
                    "genre": "AI",
                    "lyrics": suno_data.get("prompt", ""),
                    "audio_path": audio_path,
                    "cover_path": None
                }).execute()

                return {
                    "status": "saved_to_supabase",
                    "task_id": task_id,
                    "audio_path": audio_path
                }

        except:
            pass

    return {"status": "timeout_waiting_for_audio", "task_id": task_id}
