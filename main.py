from fastapi import FastAPI, HTTPException
import httpx
import os

app = FastAPI(title="Suno Music Generator")

# ======================
# CONFIG
# ======================
SUNO_TOKEN = os.getenv("SUNO_TOKEN")
if not SUNO_TOKEN:
    raise RuntimeError("SUNO_TOKEN belum diset")

API_GENERATE = "https://api.sunoapi.org/api/v1/generate"
API_RECORD_INFO = "https://api.sunoapi.org/api/v1/generate/record-info"

HEADERS = {
    "Authorization": f"Bearer {SUNO_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

# ======================
# ROOT
# ======================
@app.get("/")
def root():
    return {"status": "ok"}

# ======================
# GENERATE LAGU
# ======================
@app.post("/music/generate")
async def generate_music(body: dict):
    if "prompt" not in body:
        raise HTTPException(400, "prompt wajib ada")

    payload = {
        "prompt": body["prompt"],
        "model": "chirp-v3-5",
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            API_GENERATE,
            json=payload,
            headers=HEADERS,
        )

    if resp.status_code != 200:
        raise HTTPException(resp.status_code, resp.text)

    data = resp.json()

    task_id = data.get("data", {}).get("taskId")
    if not task_id:
        raise HTTPException(500, data)

    return {
        "taskId": task_id,
        "message": "Gunakan /music/status/{taskId} untuk ambil lagu & lirik"
    }

# ======================
# CEK STATUS + HASIL
# ======================
@app.get("/music/status/{task_id}")
async def music_status(task_id: str):
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(
            API_RECORD_INFO,
            params={"taskId": task_id},
            headers=HEADERS,
        )

    if resp.status_code != 200:
        raise HTTPException(resp.status_code, resp.text)

    data = resp.json()

    # Struktur Suno: data.records[0]
    records = data.get("data", {}).get("records", [])
    if not records:
        return {
            "status": "pending",
            "raw": data,
        }

    song = records[0]

    return {
        "status": song.get("status"),
        "title": song.get("title"),
        "lyrics": song.get("lyrics"),
        "audioUrl": song.get("audioUrl") or song.get("audio_url"),
        "imageUrl": song.get("imageUrl") or song.get("image_urfrom fastapi import FastAPI, HTTPException
import httpx
import os

app = FastAPI(title="Suno Music Generator")

# ======================
# CONFIG
# ======================
SUNO_TOKEN = os.getenv("SUNO_TOKEN")
if not SUNO_TOKEN:
    raise RuntimeError("SUNO_TOKEN belum diset")

API_GENERATE = "https://api.sunoapi.org/api/v1/generate"
API_RECORD_INFO = "https://api.sunoapi.org/api/v1/generate/record-info"

HEADERS = {
    "Authorization": f"Bearer {SUNO_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

# ======================
# ROOT
# ======================
@app.get("/")
def root():
    return {"status": "ok"}

# ======================
# GENERATE LAGU
# ======================
@app.post("/music/generate")
async def generate_music(body: dict):
    if "prompt" not in body:
        raise HTTPException(400, "prompt wajib ada")

    payload = {
        "prompt": body["prompt"],
        "model": "chirp-v3-5",
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            API_GENERATE,
            json=payload,
            headers=HEADERS,
        )

    if resp.status_code != 200:
        raise HTTPException(resp.status_code, resp.text)

    data = resp.json()

    task_id = data.get("data", {}).get("taskId")
    if not task_id:
        raise HTTPException(500, data)

    return {
        "taskId": task_id,
        "message": "Gunakan /music/status/{taskId} untuk ambil lagu & lirik"
    }

# ======================
# CEK STATUS + HASIL
# ======================
@app.get("/music/status/{task_id}")
async def music_status(task_id: str):
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(
            API_RECORD_INFO,
            params={"taskId": task_id},
            headers=HEADERS,
        )

    if resp.status_code != 200:
        raise HTTPException(resp.status_code, resp.text)

    data = resp.json()

    # Struktur Suno: data.records[0]
    records = data.get("data", {}).get("records", [])
    if not records:
        return {
            "status": "pending",
            "raw": data,
        }

    song = records[0]

    return {
        "status": song.get("status"),
        "title": song.get("title"),
        "lyrics": song.get("lyrics"),
        "audioUrl": song.get("audioUrl") or song.get("audio_url"),
        "imageUrl": song.get("imageUrl") or song.get("image_url"),
        "duration": song.get("duration"),
        "raw": song,
                            }

                            
                            }

                            
