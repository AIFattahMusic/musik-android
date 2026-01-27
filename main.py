from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import requests
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="AI Music Generator (Suno API)")

# === ENV ===
SUNO_API_URL = os.getenv("SUNO_API_URL", "https://api.sunoapi.org/api/v1/generate")
SUNO_TOKEN = os.getenv("SUNO_TOKEN")

# callback URL otomatis dari Render kamu
BASE_URL = "https://ai-music-fattah.onrender.com"
CALLBACK_URL = f"{BASE_URL}/callback"

if not SUNO_TOKEN:
    raise Exception("SUNO_TOKEN belum diisi. Set di Render -> Environment Variables")

# === In-memory storage ===
# key: taskId / id, value: callback payload
RESULTS = {}


class GenerateRequest(BaseModel):
    prompt: str
    style: str = "Classical"
    title: str = "Peaceful Piano Meditation"
    negativeTags: str = "Heavy Metal, Upbeat Drums"
    customMode: bool = True
    instrumental: bool = True
    model: str = "V3_5"


@app.get("/")
def home():
    return {
        "status": "ok",
        "service": "AI Music Generator (Suno API)",
        "generate_endpoint": "/generate",
        "callback_endpoint": "/callback",
        "check_result": "/result/{task_id}"
    }


@app.post("/generate")
def generate_music(body: GenerateRequest):
    payload = {
        "prompt": body.prompt,
        "style": body.style,
        "title": body.title,
        "customMode": body.customMode,
        "instrumental": body.instrumental,
        "model": body.model,
        "negativeTags": body.negativeTags,
        "callBackUrl": CALLBACK_URL
    }

    headers = {
        "Authorization": f"Bearer {SUNO_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    try:
        r = requests.post(SUNO_API_URL, json=payload, headers=headers, timeout=60)
        data = r.json()

        # coba ambil taskId / id kalau ada
        task_id = None
        if isinstance(data, dict):
            task_id = (
                data.get("taskId")
                or (data.get("data") or {}).get("taskId")
                or data.get("id")
                or (data.get("data") or {}).get("id")
            )

        return {
            "callbackUrl": CALLBACK_URL,
            "taskId_guess": task_id,
            "suno_response": data
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/callback")
async def callback(request: Request):
    data = await request.json()

    # cari taskId / id dari callback payload
    task_id = (
        data.get("taskId")
        or (data.get("data") or {}).get("taskId")
        or data.get("id")
        or (data.get("data") or {}).get("id")
    )

    # kalau tidak ada id, simpan pakai key "latest"
    key = task_id if task_id else "latest"
    RESULTS[key] = data

    print("=== CALLBACK FROM SUNO ===")
    print(data)

    return {"status": "ok", "saved_as": key}


@app.get("/result/{task_id}")
def get_result(task_id: str):
    if task_id not in RESULTS:
        raise HTTPException(status_code=404, detail="Belum ada hasil callback untuk taskId ini")
    return RESULTS[task_id]


@app.get("/result-latest")
def get_latest_result():
    if "latest" not in RESULTS:
        raise HTTPException(status_code=404, detail="Belum ada callback masuk")
    return RESULTS["latest"]
