import os
 math
import waveimport
import struct
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="Simple Music Generator")

# Render AMAN nulis di /tmp
AUDIO_DIR = "/tmp/audio"
os.makedirs(AUDIO_DIR, exist_ok=True)

class GenerateRequest(BaseModel):
    duration: int = 5  # detik (default 5)


@app.get("/")
def root():
    return {
        "status": "ok",
        "endpoints": {
            "generate": "POST /generate",
            "download": "GET /download/{audio_id}"
        }
    }


def generate_wav(path: str, duration: int):
    framerate = 44100
    frequency = 440  # nada A
    amplitude = 12000

    with wave.open(path, "w") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(framerate)

        for i in range(duration * framerate):
            value = int(amplitude * math.sin(2 * math.pi * frequency * i / framerate))
            wav.writeframes(struct.pack("<h", value))


@app.post("/generate")
def generate(req: GenerateRequest):
    if req.duration <= 0 or req.duration > 30:
        raise HTTPException(400, "duration must be 1–30 seconds")

    audio_id = str(uuid.uuid4())
    filepath = os.path.join(AUDIO_DIR, f"{audio_id}.wav")

    generate_wav(filepath, req.duration)

    return {
        "success": True,
        "audio_id": audio_id,
        "download_url": f"/download/{audio_id}"
    }


@app.get("/download/{audio_id}")
def download(audio_id: str):
    filepath = os.path.join(AUDIO_DIR, f"{audio_id}.wav")
    if not os.path.exists(filepath):
        raise HTTPException(404, "Audio not found")

    return FileResponse(
        filepath,
        media_type="audio/wav",
        filename=f"{audio_id}.wav"
    )


