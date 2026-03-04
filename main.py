import os
import uuid
import asyncio
import requests
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from supabase import create_client

# ================== ENV ==================

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

app = FastAPI(title="AI Music Auto Supabase", version="5.0")

# ================== MODEL ==================

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

# ================== AUTO GENERATE ==================

@app.post("/generate-music")
async def generate_music(payload: GenerateMusicRequest):

    # Step 1 — Create task
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

    # Step 2 — Polling until finished
    for _ in range(30):  # max 30 attempts (±150 seconds)
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
            state = suno_data.get("state")
            audio_url = suno_data.get("audioUrl")

            if state == "succeeded" and audio_url:

                # Step 3 — Download audio
                audio_bytes = requests.get(audio_url).content

                # Step 4 — Upload to Supabase
                file_id = str(uuid.uuid4())
                audio_path = f"songs/{file_id}.mp3"

                supabase.storage.from_("music").upload(
                    audio_path,
                    audio_bytes,
                    {"upsert": True}
                )

                # Step 5 — Insert to database
                supabase.table("songs").insert({
                    "title": suno_data.get("title", "Untitled"),
                    "artist": "AI Generator",
                    "genre": "AI",
                    "lyrics": suno_data.get("prompt", ""),
                    "audio_path": audio_path,
                    "cover_path": None
                }).execute()

                return {
                    "status": "success",
                    "task_id": task_id,
                    "audio_path": audio_path
                }

        except Exception as e:
            print("Polling error:", e)

    return {
        "status": "timeout",
        "task_id": task_id
    }
