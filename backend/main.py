import os
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response

app = FastAPI(title="73Bot TTS Backend", version="1.0.0")

COEIROINK_URL = os.getenv("COEIROINK_URL", "http://coeiroink:50031")
# Default speaker settings for COEIROINK v2 (e.g. dummy UUID/style; user may need to adjust)
SPEAKER_UUID = os.getenv("SPEAKER_UUID", "388f246b-8c41-4ac1-8e2d-5d79f3ff56d9")
STYLE_ID = int(os.getenv("STYLE_ID", "21"))

@app.get("/")
async def root():
    return {"status": "ok", "service": "tts-backend", "coeiroink_url": COEIROINK_URL}

@app.post("/synthesize")
async def generate_audio(text: str):
    """
    Sends text to COEIROINK to generate speech audio and returns the WAV bytes.
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 1. Create audio query
            query_res = await client.post(
                f"{COEIROINK_URL}/v1/audio_query",
                json={"text": text, "speakerUuid": SPEAKER_UUID, "styleId": STYLE_ID}
            )
            query_res.raise_for_status()
            query_data = query_res.json()

            # 2. Synthesize audio
            synth_res = await client.post(
                f"{COEIROINK_URL}/v1/synthesis",
                json={"speakerUuid": SPEAKER_UUID, "styleId": STYLE_ID, "audioQuery": query_data},
                headers={"Content-Type": "application/json"}
            )
            synth_res.raise_for_status()
            
            # Return WAV data
            return Response(content=synth_res.content, media_type="audio/wav")
            
    except httpx.RequestError as exc:
        raise HTTPException(status_code=500, detail=f"Request to COEIROINK API failed: {exc}")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=f"COEIROINK API returned error: {exc}")
