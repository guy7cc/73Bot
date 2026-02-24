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
# Default speaker name pattern: "SpeakerName (StyleName)"
DEFAULT_SPEAKER_NAME = os.getenv("DEFAULT_SPEAKER_NAME", "リリンちゃん (のーまる)")

class SpeakerManager:
    def __init__(self, url: str):
        self.url = url
        self.styles = {} # "Name (Style)": id
        self.default_id = 90 # Fallback safety

    async def refresh(self):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{self.url}/speakers")
                res.raise_for_status()
                speakers = res.json()
                
                new_styles = {}
                for s in speakers:
                    speaker_name = s.get("name")
                    for style in s.get("styles", []):
                        style_name = style.get("name")
                        style_id = style.get("id")
                        full_name = f"{speaker_name} ({style_name})"
                        new_styles[full_name] = style_id
                
                if new_styles:
                    self.styles = new_styles
                    # Determine default
                    if DEFAULT_SPEAKER_NAME in self.styles:
                        self.default_id = self.styles[DEFAULT_SPEAKER_NAME]
                    else:
                        # Fallback to alphabetical first
                        sorted_names = sorted(self.styles.keys())
                        self.default_id = self.styles[sorted_names[0]]
                    return True
        except Exception as e:
            print(f"Error refreshing speakers: {e}")
        return False

    def get_style_id(self, name: Optional[str] = None) -> int:
        if name and name in self.styles:
            return self.styles[name]
        return self.default_id

    def get_available_names(self) -> List[str]:
        return sorted(self.styles.keys())

speaker_manager = SpeakerManager(COEIROINK_URL)

class SynthesizeRequest(BaseModel):
    text: str
    speaker: Optional[str] = None

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
    await speaker_manager.refresh()
    speakers = speaker_manager.get_available_names()
    speaker_count = len(speakers)
    current_default = [name for name, id in speaker_manager.styles.items() if id == speaker_manager.default_id]
    default_name = current_default[0] if current_default else "Unknown"
    
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
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            .speaker-item.default {{
                border: 1px solid var(--accent);
                background: rgba(56, 189, 248, 0.1);
            }}
            .speaker-item.default::after {{
                content: 'DEFAULT';
                font-size: 0.7rem;
                font-weight: bold;
                color: var(--accent);
                background: rgba(56, 189, 248, 0.1);
                padding: 2px 6px;
                border-radius: 4px;
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
                        <p><strong>Default Voice:</strong> <span style="color: var(--accent)">{default_name}</span></p>
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
                    {"".join([f'<div class="speaker-item {"default" if name == default_name else ""}">{name}</div>' for name in speakers]) if speakers else "No speakers found."}
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
    await speaker_manager.refresh()
    speakers = speaker_manager.get_available_names()
    return {
        "status": "ok",
        "service": "73bot-tts-backend",
        "coeiroink_connection": "connected" if speakers else "failed",
        "speaker_count": len(speakers),
        "speakers": speakers,
        "default_speaker": next((name for name, id in speaker_manager.styles.items() if id == speaker_manager.default_id), None)
    }

@app.post("/synthesize")
async def generate_audio(request: SynthesizeRequest):
    """
    Sends text to COEIROINK to generate speech audio and returns the WAV bytes.
    """
    await speaker_manager.refresh()
    text = request.text
    style_id = speaker_manager.get_style_id(request.speaker)
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 1. Create audio query
            query_res = await client.post(
                f"{COEIROINK_URL}/audio_query",
                params={"text": text, "speaker": style_id}
            )
            query_res.raise_for_status()
            query_data = query_res.json()

            # 2. Synthesize audio
            synth_res = await client.post(
                f"{COEIROINK_URL}/synthesis",
                params={"speaker": style_id},
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
