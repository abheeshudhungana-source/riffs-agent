import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional
from riffs_api.routes import router as riff_routes

# Import the RIFFs agent harness
try:
    from agent import RiffsAgent
    agent = RiffsAgent()
except Exception as e:
    agent = None
    print(f"Warning: could not initialize RiffsAgent: {e}")

app = FastAPI(
    title="RIFFs Agent API",
    description="Autonomous AI Practice & Sketching Partner for Musicians",
    version="0.1.0"
)

app.include_router(riff_routes)

# Root route serves the interactive Day 0 prototype
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
        "model": "anthropic/claude-sonnet-5-5",
        "has_api_key": bool(os.getenv("ANTHROPIC_API_KEY"))
    }

class GenerateRequest(BaseModel):
    prompt: str
    key: Optional[str] = "Am"
    bpm: Optional[int] = 110
    locked_parts: Optional[list] = []

@app.post("/api/generate")
async def generate_riff(req: GenerateRequest):
    if not os.getenv("ANTHROPIC_API_KEY"):
        return {
            "status": "mock",
            "message": "ANTHROPIC_API_KEY not configured in Vercel environment variables yet.",
            "data": {
                "key": req.key,
                "bpm": req.bpm,
                "chords": ["Am", "F", "C", "G"],
                "nashville": ["1m", "4", "1", "5"],
                "tab": "e|---0-------1-------0-------3---|\nB|---1-------1-------1-------0---|\nG|---2-------2-------0-------0---|\nD|---2-------3-------2-------0---|\nA|---0-------3-------3-------2---|\nE|-----------1---------------3---|",
                "notes": "Generated Day 0 blueprint ready for playback and practice."
            }
        }
    
    if not agent:
        return JSONResponse(status_code=500, content={"error": "RiffsAgent not initialized"})

    try:
        enriched_prompt = (
            f"Generate an instrumental riff blueprint in Key: {req.key}, BPM: {req.bpm}. "
            f"Locked parts: {req.locked_parts}. Musician Prompt: {req.prompt}"
        )
        response_text = agent.run_turn(enriched_prompt)
        return {
            "status": "success",
            "response": response_text
        }
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(exc)}
        )
