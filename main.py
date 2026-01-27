from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import httpx
import os
import logging

app = FastAPI()

# logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SAVE_DIR = "generated_music"
os.makedirs(SAVE_DIR, exist_ok=True)


@app.post("/generate-music-callback")
async def generate_music_callback(request: Request):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    code = payload.get("code")
    msg = payload.get("msg", "")
    data = payload.get("data")

    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Invalid data format")

    task_id = data.get("task_id")
    callback_type = data.get("callbackType")
    musics = data.get("data")

    if not task_id or not isinstance(musics, list):
        raise HTTPException(status_code=400, detail="Missing task_id or music list")

    logger.info("=== CALLBACK MASUK ===")
    logger.info(f"Task ID: {task_id}")
    logger.info(f"Type: {callback_type}")
    logger.info(f"Code: {code}")
    logger.info(f"Message: {msg}")

    if code != 200:
        logger.error(f"Generate gagal: {msg}")
        return JSONResponse({"status": "failed", "message": msg})

    async with httpx.AsyncClient(timeout=30) as client:
        for i, music in enumerate(musics, start=1):
            title = music.get("title", f"music_{i}")
            audio_url = music.get("audio_url")

            logger.info(f"Music #{i}: {title}")

            if not audio_url:
                logger.warning("Audio URL kosong, dilewati")
                continue

            filename = f"{task_id}_{i}.mp3"
            filepath = os.path.join(SAVE_DIR, filename)

            try:
                r = await client.get(audio_url)
                r.raise_for_status()

                with open(filepath, "wb") as f:
                    f.write(r.content)

                logger.info(f"Saved: {filepath}")

            except Exception as e:
                logger.error(f"Download error ({audio_url}): {e}")

    return JSONResponse({"status": "received"})
