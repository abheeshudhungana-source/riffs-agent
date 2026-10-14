import os
from pathlib import Path
from typing import Literal, Optional, List, Dict, Any, Union
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from riffs_api.progression import ProgressionError
from riffs_api.routes import router as riff_routes
from riffs_api.prompt_guardrails import PromptRefusal

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
        "version": "0.2.0 (Audio engine)",
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
    seed: Optional[int] = None
    previous_score: Optional[Dict[str, Any]] = None
    base_take_id: Optional[int] = None
    base_storage_id: Optional[str] = None
    issue_license: Optional[bool] = True
    groove: Optional[Literal["straight", "half_time", "swing", "half_time_shuffle"]] = None
    lyrics_prompt: Optional[str] = None
    lyrics_language: Optional[str] = "en"
    vocal_style: Optional[str] = "soulful_lead"
    vocal_approved: Optional[bool] = False
    vocal_approval_token: Optional[str] = None
    edited_lyrics: Optional[Union[List[str], List[Dict[str, Any]]]] = None


ALLOWED_INSTRUMENTS = {
    "bass_guitar", "contrabass", "bass_drums", "floor_tom",
    "bongos", "rhythm_guitar", "acoustic_piano", "tenor_sax",
    "cymbals", "drum_kit", "triangle", "ukulele", "piccolo",
}
INSTRUMENT_TIERS = {
    "bass_guitar": "low", "contrabass": "low", "bass_drums": "low", "floor_tom": "low",
    "bongos": "mid", "rhythm_guitar": "mid", "acoustic_piano": "mid", "tenor_sax": "mid",
    "cymbals": "high", "drum_kit": "high", "triangle": "high", "ukulele": "high", "piccolo": "high",
}
LOCK_ALIASES = {
    "bass": {"bass_guitar", "contrabass", "bass_drums"},
    "rhythm": {"rhythm_guitar", "acoustic_piano", "ukulele"},
    "lead": {"tenor_sax", "piccolo"},
    "drums": {"bass_drums", "floor_tom", "bongos", "cymbals", "drum_kit", "triangle"},
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

    if req.seed is not None and not (0 <= req.seed <= 2147483647):
        return JSONResponse(
            status_code=422,
            content={"status": "error", "code": "SEED_RANGE", "detail": "Seed must be between 0 and 2147483647."}
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

    if req.base_take_id is not None and req.previous_score is None and req.base_storage_id is None and not any(
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
        previous_score = req.previous_score
        previous_take = None
        if req.base_storage_id:
            from riffs_api.take_store import get_take
            stored_record = get_take(req.base_storage_id)
            if stored_record is None:
                return JSONResponse(
                    status_code=404,
                    content={"status": "error", "code": "TAKE_NOT_FOUND", "detail": "No local take matches that ID."},
                )
            previous_take = stored_record["take"]
            previous_score = previous_score or previous_take.get("score")
        # The client can supply either prior score JSON or a local take storage ID.
        data = RiffsAgent().generate(
            prompt=req.prompt,
            key=req.key or "Am",
            bpm=bpm,
            chords=req.chords or "Am - F - C - G",
            instruments=instruments,
            locked_parts=req.locked_parts or [],
            seed=req.seed,
            previous_score=previous_score,
            previous_take=previous_take,
            base_take_id=req.base_take_id,
            issue_license=True if req.issue_license is None else req.issue_license,
            groove=req.groove,
            lyrics_prompt=req.lyrics_prompt,
            lyrics_language=req.lyrics_language or "en",
            vocal_style=req.vocal_style or "soulful_lead",
            vocal_approved=bool(req.vocal_approved),
            vocal_approval_token=req.vocal_approval_token,
            edited_lyrics=req.edited_lyrics,
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
    except ValueError as exc:
        return JSONResponse(
            status_code=422,
            content={
                "status": "error",
                "code": "CHORD_SYNTAX",
                "detail": str(exc)
            }
        )
    except PromptRefusal as exc:
        return JSONResponse(
            status_code=422,
            content={
                "status": "error",
                "code": exc.code,
                "detail": exc.detail,
                "alternative": exc.alternative,
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


class VocalApproveRequest(BaseModel):
    token: str
    lyrics_prompt: str
    prompt: Optional[str] = "Accompaniment with lead vocal track"
    key: Optional[str] = "Am"
    bpm: Optional[int] = 110
    chords: Optional[str] = "Am - F - C - G"
    instruments: Optional[List[str]] = Field(default_factory=lambda: ["bass_guitar", "rhythm_guitar", "cymbals"])
    edited_lyrics: Optional[Union[List[str], List[Dict[str, Any]]]] = None
    seed: Optional[int] = None
    groove: Optional[Literal["straight", "half_time", "swing", "half_time_shuffle"]] = "straight"
    vocal_style: Optional[str] = "soulful_lead"
    lyrics_language: Optional[str] = "en"


@app.post("/api/vocals/approve")
async def approve_vocal_track(req: VocalApproveRequest):
    try:
        data = RiffsAgent().generate(
            prompt=req.prompt or "Accompaniment with lead vocal track",
            key=req.key or "Am",
            bpm=req.bpm or 110,
            chords=req.chords or "Am - F - C - G",
            instruments=req.instruments or ["bass_guitar", "rhythm_guitar", "cymbals"],
            seed=req.seed,
            groove=req.groove,
            lyrics_prompt=req.lyrics_prompt,
            lyrics_language=req.lyrics_language or "en",
            vocal_style=req.vocal_style or "soulful_lead",
            vocal_approved=True,
            vocal_approval_token=req.token,
            edited_lyrics=req.edited_lyrics,
        )
        return {"status": "success", "data": data}
    except ValueError as exc:
        return JSONResponse(status_code=403, content={"status": "error", "code": "VOCAL_AUTH_FAILED", "detail": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"status": "error", "code": "VOCAL_RENDER_FAILED", "detail": str(exc)})


@app.get("/api/takes/{storage_id}")
async def get_stored_take(storage_id: str):
    """Read a take saved in this app instance's configured local folder."""
    from riffs_api.take_store import get_take
    record = get_take(storage_id)
    if record is None:
        return JSONResponse(
            status_code=404,
            content={"status": "error", "code": "TAKE_NOT_FOUND", "detail": "No local take matches that ID."},
        )
    return {"status": "success", "data": record}


class VideoRemuxRequest(BaseModel):
    video_base64: str
    audio_base64: str
    video_filename: Optional[str] = "input.mp4"
    audio_filename: Optional[str] = "riff.wav"
    output_filename: Optional[str] = None


@app.post("/api/v1/tools/attach-riff-to-video")
async def attach_video_endpoint(req: VideoRemuxRequest):
    import base64
    from riffs_api.video import attach_riff_to_video
    try:
        video_bytes = base64.b64decode(req.video_base64)
        audio_bytes = base64.b64decode(req.audio_base64)
        result = attach_riff_to_video(
            video_source=video_bytes,
            audio_source=audio_bytes,
            video_filename=req.video_filename or "input.mp4",
            audio_filename=req.audio_filename or "riff.wav",
            output_filename=req.output_filename,
        )
        return {
            "status": "success",
            "filename": result["filename"],
            "size_bytes": result["size_bytes"],
            "remux_mode": result["remux_mode"],
            "video_base64": base64.b64encode(result["content"]).decode("ascii"),
        }
    except ValueError as exc:
        return JSONResponse(
            status_code=422,
            content={"status": "error", "code": "VIDEO_VALIDATION", "detail": str(exc)},
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "code": "VIDEO_REMUX_FAILED", "detail": str(exc)},
        )


