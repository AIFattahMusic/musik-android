from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import os
import threading
import requests

app = FastAPI()

# Folder simpan musik (Render writeable, tapi non-persistent)
SAVE_DIR = os.environ.get("SAVE_DIR", "generated_music")
os.makedirs(SAVE_DIR, exist_ok=True)


def download_music(task_id: str, musics: list):
    """
    Download dijalankan di background thread
    supaya callback Suno tidak timeout
    """
    for i, music in enumerate(musics, start=1):
        audio_url = music.get("audio_url")
        if not audio_url:
            continue

        try:
            r = requests.get(audio_url, timeout=20)
            if r.status_code == 200:
                filename = f"{task_id}_{i}.mp3"
                filepath = os.path.join(SAVE_DIR, filename)
                with open(filepath, "wb") as f:
                    f.write(r.content)
                print("Saved:", filepath)
        except Exception as e:
            print("Download error:", e)


@app.get("/")
def root():
    return {"status": "ok"}


# 🚨 INI CALLBACK YANG HARUS KAMU SET DI SUNO
@app.post("/generate-music-callback")
async def generate_music_callback(request: Request):
    payload = await request.json()

    code = payload.get("code")
    msg = payload.get("msg", "")
    data = payload.get("data", {})

    callback_type = data.get("callbackType")
    task_id = data.get("task_id")
    musics = data.get("data", [])

    print("=== SUNO CALLBACK MASUK ===")
    print("Task ID:", task_id)
    print("Callback Type:", callback_type)
    print("Code:", code)
    print("Message:", msg)

    # 🚨 WAJIB: balas 200 CEPAT
    response = JSONResponse({"status": "received"}, status_code=200)

    # Download HANYA saat complete & sukses
    if code == 200 and callback_type == "complete":
        threading.Thread(
            target=download_music,
            args=(task_id, musics),
            daemon=True
        ).start()

    return response
