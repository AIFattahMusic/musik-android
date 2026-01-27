def home():
    return {
        "status": "ok",
        "generate": "/generate",
        "callback": "/callback",
        "check_status": "/music/status",
        "callback_url_used": CALLBACK_URL
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
        resp = r.json()
        task_id = guess_task_id(resp)

