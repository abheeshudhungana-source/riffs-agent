import os
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

# Import the RIFFs agent harness
try:
    from agent import RiffsAgent
    agent = RiffsAgent()
except Exception as e:
    agent = None
    print(f"Warning: could not initialize RiffsAgent: {e}")

app = FastAPI(
    title="RIFFs Agent API",
    description="Autonomous AI Practice & Sketching Partner for Musicians (Day 1 Milestone)",
    version="0.1.0"
)

# Root route serves the interactive prototype
@app.get("/", response_class=HTMLResponse)
async def get_index():
    index_file = Path(__file__).parent / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>RIFFs Agent Prototype</h1><p>index.html not found.</p>")

# Health check endpoint
@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "app": "RIFFs Agent",
        "version": "0.1.0 (Day 1)",
        "model": "anthropic/claude-sonnet-5-5",
        "has_api_key": bool(os.getenv("ANTHROPIC_API_KEY"))
    }

class GenerateRequest(BaseModel):
    prompt: str
    key: Optional[str] = "Am"
    bpm: Optional[int] = 110
    chords: Optional[str] = "Am - F - C - G"
    instruments: Optional[List[str]] = ["bass_guitar", "rhythm_guitar", "cymbals"]
    locked_parts: Optional[List[str]] = []

@app.post("/api/generate")
async def generate_riff(req: GenerateRequest):
    # Server-side boundary validations (Deliverable 3 error handling table)
    instruments = req.instruments or []
    if len(instruments) < 1 or len(instruments) > 3:
        return JSONResponse(
            status_code=422,
            content={
                "status": "error",
                "code": "INSTRUMENT_COUNT",
                "detail": "Select 1 to 3 instruments (1 per tier)."
            }
        )

    bpm = req.bpm if req.bpm is not None else 110
    if bpm < 60 or bpm > 200:
        return JSONResponse(
            status_code=422,
            content={
                "status": "error",
                "code": "BPM_RANGE",
                "detail": "Tempo must be between 60 and 200 BPM."
            }
        )

    if not agent:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "code": "AGENT_INIT_FAILED",
                "detail": "RiffsAgent harness could not be initialized."
            }
        )

    try:
        data = agent.generate(
            prompt=req.prompt,
            key=req.key or "Am",
            bpm=bpm,
            chords=req.chords or "Am - F - C - G",
            instruments=instruments,
            locked_parts=req.locked_parts or []
        )
        return {
            "status": "success",
            "data": data
        }
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "code": "GENERATION_ERROR",
                "detail": str(exc)
            }
        )
