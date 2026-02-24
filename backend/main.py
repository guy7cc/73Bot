import os
import httpx
import docker
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response, HTMLResponse
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="73Bot TTS Backend", version="1.2.0")

COEIROINK_URL = os.getenv("COEIROINK_URL", "http://coeiroink:50031")
COEIROINK_CONTAINER = os.getenv("COEIROINK_CONTAINER", "coeiroink-v2")
# Default for "リリンちゃん" style "のーまる"
SPEAKER_UUID = os.getenv("SPEAKER_UUID", "cb11bdbd-78fc-4f16-b528-a400bae1782d")
STYLE_ID = int(os.getenv("STYLE_ID", "90"))

class SynthesizeRequest(BaseModel):
    text: str

async def get_speakers():
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get(f"{COEIROINK_URL}/speakers")
            res.raise_for_status()
            return res.json()
    except Exception:
        return []

@app.post("/restart-coeiroink")
async def restart_coeiroink():
    try:
        client = docker.from_env()
        container = client.containers.get(COEIROINK_CONTAINER)
        container.restart()
        return {"status": "success", "message": f"Container {COEIROINK_CONTAINER} is restarting..."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to restart container: {e}")

@app.get("/", response_class=HTMLResponse)
async def root():
    speakers = await get_speakers()
    speaker_count = len(speakers)
    
    # Simple dashboard with rich aesthetics
    html_content = f"""
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>73Bot TTS Dashboard</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap" rel="stylesheet">
        <style>
            :root {{
                --bg: #0f172a;
                --card-bg: #1e293b;
                --accent: #38bdf8;
                --text: #f8fafc;
                --success: #22c55e;
                --warning: #f59e0b;
                --danger: #ef4444;
            }}
            body {{
                font-family: 'Inter', sans-serif;
                background-color: var(--bg);
                color: var(--text);
                margin: 0;
                padding: 40px;
                display: flex;
                flex-direction: column;
                align-items: center;
            }}
            .container {{
                max-width: 800px;
                width: 100%;
            }}
            .card {{
                background-color: var(--card-bg);
                border-radius: 16px;
                padding: 24px;
                box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
                border: 1px solid rgba(255, 255, 255, 0.1);
                margin-bottom: 24px;
            }}
            h1 {{
                font-size: 2.5rem;
                margin-bottom: 0.5rem;
                background: linear-gradient(to right, #38bdf8, #818cf8);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }}
            .status-badge {{
                display: inline-flex;
                align-items: center;
                padding: 4px 12px;
                border-radius: 9999px;
                font-size: 0.875rem;
                font-weight: bold;
                background-color: rgba(34, 197, 94, 0.2);
                color: var(--success);
            }}
            .speaker-list {{
                margin-top: 20px;
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
                gap: 12px;
            }}
            .speaker-item {{
                background: rgba(255, 255, 255, 0.05);
                padding: 12px;
                border-radius: 8px;
                font-size: 0.9rem;
            }}
            .btn {{
                background-color: var(--accent);
                color: var(--bg);
                border: none;
                padding: 10px 20px;
                border-radius: 8px;
                font-weight: bold;
                cursor: pointer;
                transition: opacity 0.2s;
                margin-top: 10px;
            }}
            .btn:hover {{ opacity: 0.9; }}
            .btn-restart {{ background-color: var(--warning); }}
            #message {{ margin-top: 10px; font-size: 0.9rem; }}
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>73Bot Monitoring</h1>
                <div class="status-badge">● System Online</div>
            </header>
            
            <div class="card" style="margin-top: 40px;">
                <h2>Service Status</h2>
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <p><strong>Backend:</strong> <span style="color: var(--success)">Healthy</span></p>
                        <p><strong>COEIROINK:</strong> {COEIROINK_URL}</p>
                        <p><strong>Available Voices:</strong> {speaker_count}</p>
                    </div>
                    <div>
                        <button onclick="restartCoeiroink()" class="btn btn-restart">Restart COEIROINK</button>
                        <div id="message"></div>
                    </div>
                </div>
            </div>

            <div class="card">
                <h2>Available Voice Speakers</h2>
                <div class="speaker-list">
                    {"".join([f'<div class="speaker-item">{s.get("name")}</div>' for s in speakers]) if speakers else "No speakers found."}
                </div>
            </div>
        </div>

        <script>
            async function restartCoeiroink() {{
                const msg = document.getElementById('message');
                msg.innerText = 'Restarting...';
                msg.style.color = 'var(--warning)';
                try {{
                    const res = await fetch('/restart-coeiroink', {{ method: 'POST' }});
                    const data = await res.json();
                    if (res.ok) {{
                        msg.innerText = 'Restart signal sent successfully.';
                        msg.style.color = 'var(--success)';
                        setTimeout(() => location.reload(), 5000);
                    }} else {{
                        msg.innerText = 'Error: ' + data.detail;
                        msg.style.color = 'var(--danger)';
                    }}
                }} catch (e) {{
                    msg.innerText = 'Failed to connect to backend.';
                    msg.style.color = 'var(--danger)';
                }}
            }}
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/status")
async def status():
    speakers = await get_speakers()
    return {
        "status": "ok",
        "service": "73bot-tts-backend",
        "coeiroink_connection": "connected" if speakers else "failed",
        "speaker_count": len(speakers),
        "speakers": [s.get("name") for s in speakers]
    }

@app.post("/synthesize")
async def generate_audio(request: SynthesizeRequest):
    """
    Sends text to COEIROINK to generate speech audio and returns the WAV bytes.
    """
    text = request.text
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 1. Create audio query
            query_res = await client.post(
                f"{COEIROINK_URL}/audio_query",
                params={"text": text, "speaker": STYLE_ID}
            )
            query_res.raise_for_status()
            query_data = query_res.json()

            # 2. Synthesize audio
            synth_res = await client.post(
                f"{COEIROINK_URL}/synthesis",
                params={"speaker": STYLE_ID},
                json=query_data,
                headers={"Content-Type": "application/json"}
            )
            synth_res.raise_for_status()
            
            # Return WAV data
            return Response(content=synth_res.content, media_type="audio/wav")
            
    except httpx.RequestError as exc:
        raise HTTPException(status_code=500, detail=f"Request to COEIROINK API failed: {exc}")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=f"COEIROINK API returned error: {exc}")
