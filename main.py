‎import os
‎import httpx
‎import requests
‎import psycopg2
‎from fastapi import FastAPI, Request, HTTPException
‎from fastapi.staticfiles import StaticFiles
‎from pydantic import BaseModel
‎from typing import Optional
‎
‎# ==================================================
‎# WAJIB PALING ATAS: BUAT FOLDER MEDIA
‎# ==================================================
‎os.makedirs("media", exist_ok=True)
‎
‎# ================= ENV =================
‎SUNO_API_KEY = os.getenv("SUNO_API_KEY")
‎
‎BASE_URL = os.getenv(
‎    "BASE_URL",
‎    "https://musik-android.onrender.com"
‎)
‎
‎CALLBACK_URL = f"{BASE_URL}/callback"
‎
‎SUNO_BASE_API = "https://api.kie.ai/api/v1"
‎STYLE_GENERATE_URL = f"{SUNO_BASE_API}/style/generate"
‎MUSIC_GENERATE_URL = f"{SUNO_BASE_API}/generate"
‎STATUS_URL = f"{SUNO_BASE_API}/generate/record-info"
‎
‎# ================= APP =================
‎app = FastAPI(
‎    title="AI Music Suno API Wrapper",
‎    version="1.0.2"
‎)
‎
‎# ==================================================
‎# STATIC FILES (SETELAH app dibuat)
‎# ==================================================
‎app.mount("/media", StaticFiles(directory="media"), name="media")
‎
‎# ================= REQUEST MODEL =================
‎class BoostStyleRequest(BaseModel):
‎    content: str
‎
‎class GenerateMusicRequest(BaseModel):
‎    prompt: str
‎    style: Optional[str] = None
‎    title: Optional[str] = None
‎    instrumental: bool = False
‎    customMode: bool = False
‎    model: str = "V4_5"
‎
‎# ================= HELPERS =================
‎def suno_headers():
‎    if not SUNO_API_KEY:
‎        raise HTTPException(
‎            status_code=500,
‎            detail="SUNO_API_KEY not set in environment"
‎        )
‎    return {
‎        "Authorization": f"Bearer {SUNO_API_KEY}",
‎        "Content-Type": "application/json"
‎    }
‎
‎# ================= ENDPOINTS =================
‎@app.get("/")
‎def root():
‎    return {"status": "running", "service": "AI Music Suno API"}
‎
‎@app.get("/health")
‎def health():
‎    return {"status": "ok"}
‎
‎@app.post("/boost-style")
‎async def boost_style(payload: BoostStyleRequest):
‎    async with httpx.AsyncClient(timeout=60) as client:
‎        res = await client.post(
‎            STYLE_GENERATE_URL,
‎            headers=suno_headers(),
‎            json={"content": payload.content}
‎        )
‎    return res.json()
‎
‎@app.post("/generate-music")
‎async def generate_music(payload: GenerateMusicRequest):
‎    body = {
‎        "prompt": payload.prompt,
‎        "customMode": payload.customMode,
‎        "instrumental": payload.instrumental,
‎        "model": payload.model,
‎        "callBackUrl": CALLBACK_URL
‎    }
‎
‎    if payload.style:
‎        body["style"] = payload.style
‎    if payload.title:
‎        body["title"] = payload.title
‎
‎    async with httpx.AsyncClient(timeout=60) as client:
‎        res = await client.post(
‎            MUSIC_GENERATE_URL,
‎            headers=suno_headers(),
‎            json=body
‎        )
‎    return res.json()
‎
‎@app.get("/record-info/{task_id}")
‎async def record_info(task_id: str):
‎    async with httpx.AsyncClient(timeout=30) as client:
‎        res = await client.get(
‎            STATUS_URL,
‎            headers=suno_headers(),
‎            params={"taskId": task_id}
‎        )
‎    return res.json()
‎
‎@app.post("/callback")
‎async def callback(request: Request):
‎    data = await request.json()
‎    print("SUNO CALLBACK:", data)
‎    return {"status": "received"}
‎
‎@app.get("/generate/status/{task_id}")
‎def generate_status(task_id: str):
‎    r = requests.get(
‎        STATUS_URL,
‎        headers=suno_headers(),
‎        params={"taskId": task_id}
‎    )
‎
‎    if r.status_code != 200:
‎        raise HTTPException(status_code=404, detail=r.text)
‎
‎    res = r.json()
‎
‎    item = None
‎    if isinstance(res.get("data"), list) and len(res["data"]) > 0:
‎        item = res["data"][0]
‎
‎    if not item:
‎        return {"status": "processing", "result": res}
‎
‎    state = item.get("state") or item.get("status")
‎    audio_url = (
‎        item.get("audio_url")
‎        or item.get("audioUrl")
‎        or item.get("audio")
‎    )
‎
‎    if state == "succeeded" and audio_url:
‎        audio_bytes = requests.get(audio_url).content
‎
‎        file_path = "media/song_1.mp3"
‎        with open(file_path, "wb") as f:
‎            f.write(audio_bytes)
‎
‎        return {
‎            "status": "done",
‎            "audio_url": f"{BASE_URL}/media/song_1.mp3",
‎            "result": item
‎        }
‎
‎    return {"status": "processing", "result": item}
‎
‎# ================= DB TEST =================
‎def get_conn():
‎    return psycopg2.connect(os.environ["DATABASE_URL"])
‎
‎@app.get("/db-all")
‎def db_all():
‎    conn = get_conn()
‎    cur = conn.cursor()
‎    cur.execute("""
‎        SELECT *
‎        FROM information_schema.tables
‎        WHERE table_schema = 'public';
‎    """)
‎    rows = cur.fetchall()
‎    cur.close()
‎    conn.close()
‎    return rows
‎
