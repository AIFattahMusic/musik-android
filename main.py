from fastapi import FastAPI, HTTPException
import httpx
import os

app = FastAPI()

# ======================
# CONFIG
# ======================
SUNO_TOKEN = os.getenv("SUNO_TOKEN")
if not SUNO_TOKEN:
    raise RuntimeError("SUNO_TOKEN belum diset")

API_GENERATE = "https://api.sunoapi.org/api/v1/generate"
API_STATUS = "https://api.sunoapi.org/api/v1/status"

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
            headers={
                "Authorization": f"Bearer {SUNO_TOKEN}",
                "Accept": "application/json",
            },
        )

    if resp.status_code >= 400:
        raise HTTPException(resp.status_code, resp.text)

    data = resp.json()

    task_id = (
        data.get("taskId")
        or data.get("data", {}).get("taskId")
        or data.get("data", {}).get("task_id")
    )

    if not task_id:
        raise HTTPException(500, data)

    return {
        "taskId": task_id,
        "note": "Gunakan /music/status/{taskId} untuk ambil lagu & lirik"
    }

# ======================
# CEK STATUS + HASIL
# ======================
@app.get("/music/status/{task_id}")
async def music_status(task_id: str):
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(
            f"{API_STATUS}/{task_id}",
            headers={
                "Authorization": f"Bearer {SUNO_TOKEN}",
                "Accept": "application/json",
            },
        )

    if resp.status_code >= 400:
        raise HTTPException(resp.status_code, resp.text)

    data = resp.json()

    return data            status_code=502,
            detail=f"Tidak ada taskId dari Suno: {data}",
        )

    music_tasks[task_id] = {
        "status": "pending",
        "title": body.title,
    }

    return {
        "status": "queued",
        "taskId": task_id,
    }

    try:
        data = resp.json()
    except Exception:
        raise HTTPException(
            status_code=502,
            detail=f"Suno balas non-JSON: {resp.text}",
        )
@app.get("/music/status/{task_id}")
def get_music_status(task_id: str):
    task = music_tasks.get(task_id)

    if not task:
        raise HTTPException(
            status_code=404,
            detail="Task ID tidak ditemukan",
        )

    return {
        "taskId": task_id,
        "status": task["status"],
        "data": task.get("data"),
    }
    task_id = (
        data.get("taskId")
        or data.get("data", {}).get("taskId")
        or data.get("data", {}).get("task_id")
    )

    if not task_id:
        raise HTTPException(
            status_code=502,
            detail=f"Tidak ada taskId dari Suno: {data}",
        )

    # Simpan task
    music_tasks[task_id] = {
        "status": "pending",
        "prompt": body.prompt,
        "title": body.title,
    }

    return {
        "status": "queued",
        "taskId": task_id,
    }




