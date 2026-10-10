import os
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from riffs_api.progression import ProgressionError
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
    description="Autonomous AI Practice & Sketching Partner for Musicians (Day 1 Milestone)",
    version="0.1.0"
)
app.include_router(riff_routes)

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
    instruments: Optional[List[str]] = Field(default_factory=lambda: ["bass_guitar", "rhythm_guitar", "cymbals"])
    locked_parts: Optional[List[str]] = Field(default_factory=list)
    base_take_id: Optional[int] = None


ALLOWED_INSTRUMENTS = {
    "bass_guitar", "contrabass", "bass_drums", "floor_tom",
    "bongos", "rhythm_guitar", "acoustic_piano", "tenor_sax",
    "cymbals", "triangle", "ukulele", "piccolo",
}
INSTRUMENT_TIERS = {
    "bass_guitar": "low", "contrabass": "low", "bass_drums": "low", "floor_tom": "low",
    "bongos": "mid", "rhythm_guitar": "mid", "acoustic_piano": "mid", "tenor_sax": "mid",
    "cymbals": "high", "triangle": "high", "ukulele": "high", "piccolo": "high",
}
LOCK_ALIASES = {
    "bass": {"bass_guitar", "contrabass", "bass_drums"},
    "rhythm": {"rhythm_guitar", "acoustic_piano", "ukulele"},
    "lead": {"tenor_sax", "piccolo"},
    "drums": {"bass_drums", "floor_tom", "bongos", "cymbals", "triangle"},
}

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

    unsupported = sorted(set(instruments) - ALLOWED_INSTRUMENTS)
    if unsupported:
        return JSONResponse(
            status_code=422,
            content={
                "status": "error",
                "code": "UNSUPPORTED_INSTRUMENT",
                "detail": f"Unsupported instrument selection: {', '.join(unsupported)}.",
            },
        )

    if len(set(instruments)) != len(instruments):
        return JSONResponse(
            status_code=422,
            content={
                "status": "error",
                "code": "DUPLICATE_INSTRUMENT",
                "detail": "Choose each instrument only once.",
            },
        )

    selected_tiers = [INSTRUMENT_TIERS[instrument] for instrument in instruments]
    if len(set(selected_tiers)) != len(selected_tiers):
        return JSONResponse(
            status_code=422,
            content={
                "status": "error",
                "code": "INSTRUMENT_TIER_CONFLICT",
                "detail": "Choose no more than one instrument from each register tier.",
            },
        )

    requested_locks = req.locked_parts or []
    unmatched_locks = [
        lock for lock in requested_locks
        if not any(
            lock.lower() == instrument.lower()
            or lock.lower() in instrument.lower()
            or instrument.lower() in LOCK_ALIASES.get(lock.lower(), set())
            for instrument in instruments
        )
    ]
    if unmatched_locks:
        return JSONResponse(
            status_code=422,
            content={
                "status": "error",
                "code": "LOCKED_PART_NOT_SELECTED",
                "detail": f"Locked part is not selected: {', '.join(unmatched_locks)}.",
            },
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

    if req.base_take_id is not None and not any(
        take["take_id"] == req.base_take_id for take in agent.take_history
    ):
        return JSONResponse(
            status_code=422,
            content={
                "status": "error",
                "code": "TAKE_NOT_FOUND",
                "detail": "The selected take is no longer available in this server process.",
            },
        )

    try:
        data = agent.generate(
            prompt=req.prompt,
            key=req.key or "Am",
            bpm=bpm,
            chords=req.chords or "Am - F - C - G",
            instruments=instruments,
            locked_parts=req.locked_parts or [],
            base_take_id=req.base_take_id,
        )
        return {
            "status": "success",
            "data": data
        }
    except ProgressionError as exc:
        return JSONResponse(
            status_code=422,
            content={
                "status": "error",
                "code": "PROGRESSION_INVALID",
                "detail": str(exc),
            },
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "code": "GENERATION_ERROR",
                "detail": str(exc)
            }
        )
