import os
from fastapi import FastAPI
import httpx

app = FastAPI(title="73Bot TTS Backend", version="1.0.0")

COEIROINK_API_URL = os.getenv("COEIROINK_API_URL", "http://localhost:50032")

@app.get("/")
async def root():
    return {"status": "ok", "service": "tts-backend", "coeiroink_url": COEIROINK_API_URL}

@app.post("/generate")
async def generate_audio(text: str):
    # Dummy implementation for now, will implement actual COEIROINK call here
    return {"message": f"Received text: {text}", "status": "Not implemented"}
