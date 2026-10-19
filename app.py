from __future__ import annotations

import os
import base64
import binascii
import hashlib
import hmac
import json
import math
import re
import secrets
import time
from pathlib import Path
from typing import Literal, Optional, List, Dict, Any, Union
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from riffs_api.progression import ProgressionError
from riffs_api.routes import router as riff_routes
from riffs_api.prompt_guardrails import PromptRefusal
from riffs_api import storage


def _decode_jwt_segment(segment: str) -> bytes:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", segment):
        raise ValueError("Malformed token segment")
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


LOCAL_DEMO_ISSUER = "riffs-local-demo"
LOCAL_DEMO_AUDIENCE = "riffs-local-api"
_LOCAL_DEMO_JWT_SECRET = secrets.token_urlsafe(48)
_SERVERLESS_DEMO_JWT_SECRET = hashlib.sha256(
    (
        os.getenv("VERCEL_GIT_COMMIT_SHA")
        or os.getenv("VERCEL_URL")
        or "riffs-serverless-default-jwt-secret-key-2026"
    ).encode("utf-8")
).hexdigest()


def _is_deployed_environment() -> bool:
    return bool(
        os.getenv("VERCEL")
        or os.getenv("VERCEL_ENV")
        or os.getenv("AWS_LAMBDA_FUNCTION_NAME")
        or os.getenv("ENVIRONMENT", "").lower() == "production"
    )


def _has_serverless_fallback() -> bool:
    return bool(
        os.getenv("RIFFS_ALLOW_SERVERLESS_FALLBACK", "").strip().lower() in {"1", "true", "yes"}
        or os.getenv("VERCEL_URL")
        or os.getenv("VERCEL_REGION")
    )


def _demo_auth_enabled() -> bool:
    if _has_serverless_fallback():
        return True
    enabled = os.getenv("RIFFS_ENABLE_DEMO_AUTH", "").strip().lower() in {"1", "true", "yes"}
    return enabled and not _is_deployed_environment()


def _jwt_settings() -> tuple[Optional[str], Optional[str], Optional[str]]:
    secret = os.getenv("RIFFS_JWT_SECRET")
    issuer = os.getenv("RIFFS_JWT_ISSUER")
    audience = os.getenv("RIFFS_JWT_AUDIENCE")
    if _demo_auth_enabled():
        fallback_secret = _SERVERLESS_DEMO_JWT_SECRET if _has_serverless_fallback() else _LOCAL_DEMO_JWT_SECRET
        secret = secret or fallback_secret
        issuer = issuer or LOCAL_DEMO_ISSUER
        audience = audience or LOCAL_DEMO_AUDIENCE
    return secret, issuer, audience


def issue_jwt_token(
    sub: str = "beta-tester-user",
    roles: Optional[List[str]] = None,
    entitlements: Optional[List[str]] = None,
    expires_in: int = 86400,
) -> str:
    if not _demo_auth_enabled():
        raise RuntimeError("Only local demo authentication may issue test tokens")
    secret, issuer, audience = _jwt_settings()
    if not secret or not issuer or not audience or len(secret.encode("utf-8")) < 32:
        raise RuntimeError("JWT signing is not configured")
    header = {"alg": "HS256", "typ": "JWT"}
    claims = {
        "sub": sub,
        "iss": issuer,
        "aud": audience,
        "exp": time.time() + expires_in,
        "roles": roles or ["beta_tester"],
        "entitlements": entitlements or ["generation"],
    }

    def encode(value):
        return base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).decode().rstrip("=")

    header_segment = encode(header)
    claims_segment = encode(claims)
    signed = f"{header_segment}.{claims_segment}".encode("ascii")
    signature = base64.urlsafe_b64encode(hmac.new(secret.encode(), signed, hashlib.sha256).digest()).decode().rstrip("=")
    return f"{header_segment}.{claims_segment}.{signature}"


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify an HS256 access token; fail closed when auth is not configured."""
    secret, issuer, audience = _jwt_settings()
    if not secret or len(secret.encode("utf-8")) < 32 or not issuer or not audience:
        return None
    try:
        header_segment, claims_segment, signature_segment = token.split(".")
        header = json.loads(_decode_jwt_segment(header_segment))
        claims = json.loads(_decode_jwt_segment(claims_segment))
        if (not isinstance(header, dict) or header.get("alg") != "HS256"
                or header.get("typ") not in (None, "JWT") or set(header) - {"alg", "typ"}):
            return None
        if not isinstance(claims, dict):
            return None
        signed = f"{header_segment}.{claims_segment}".encode("ascii")
        expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _decode_jwt_segment(signature_segment)):
            return None
        now = time.time()
        exp = claims.get("exp")
        if isinstance(exp, bool) or not isinstance(exp, (int, float)) or not math.isfinite(exp) or exp <= now:
            return None
        nbf = claims.get("nbf")
        if nbf is not None and (isinstance(nbf, bool) or not isinstance(nbf, (int, float))
                                or not math.isfinite(nbf) or nbf > now):
            return None
        if claims.get("iss") != issuer:
            return None
        claim_aud = claims.get("aud")
        if audience not in (claim_aud if isinstance(claim_aud, list) else [claim_aud]):
            return None
        if not isinstance(claims.get("sub"), str) or not claims["sub"].strip():
            return None
        if not isinstance(claims.get("roles", []), list) or not isinstance(claims.get("entitlements", []), list):
            return None
        return claims
    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError, binascii.Error):
        return None


RATE_LIMIT = 10
RATE_WINDOW_SECONDS = 60
_RATE_LIMIT_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return count
"""
_IN_MEMORY_RATE_LIMITS: Dict[str, tuple[int, int]] = {}


def increment_generation_count(user: str, now: Optional[float] = None) -> int:
    now = time.time() if now is None else now
    window = int(now // RATE_WINDOW_SECONDS)
    user_key = hashlib.sha256(user.encode("utf-8")).hexdigest()[:32]
    key = f"rl:generation:{user_key}:{window}"
    try:
        redis_client = storage.get_redis()
        return int(redis_client.eval(_RATE_LIMIT_SCRIPT, 1, key, RATE_WINDOW_SECONDS))
    except Exception as exc:
        if not os.getenv("REDIS_URL"):
            if _is_deployed_environment() and not _has_serverless_fallback():
                raise RuntimeError("Shared Redis rate limiting is required in deployed environments") from exc
            prev_window, count = _IN_MEMORY_RATE_LIMITS.get(user_key, (window, 0))
            if prev_window != window:
                count = 1
            else:
                count += 1
            _IN_MEMORY_RATE_LIMITS[user_key] = (window, count)
            return count
        raise exc


def require_generation(authorization: Optional[str] = Header(default=None)) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(401, "Valid bearer token required", headers={"WWW-Authenticate": "Bearer"})
    claims = verify_token(token.strip())
    if not claims:
        raise HTTPException(401, "Invalid or expired token", headers={"WWW-Authenticate": "Bearer"})
    if "beta_tester" not in claims.get("roles", []) or "generation" not in claims.get("entitlements", []):
        raise HTTPException(403, "Generation entitlement required")
    now = time.time()
    try:
        count = increment_generation_count(claims["sub"], now)
    except Exception as exc:
        raise HTTPException(503, "Rate-limit service unavailable") from exc
    if count > RATE_LIMIT:
        retry_after = max(1, RATE_WINDOW_SECONDS - int(now % RATE_WINDOW_SECONDS))
        raise HTTPException(429, "Rate limit exceeded", headers={"Retry-After": str(retry_after)})
    return claims["sub"]


generation_router = APIRouter()

# Import the RIFFs agent harness
try:
    from agent import RiffsAgent, VocalApprovalError
    agent = RiffsAgent()
except Exception as e:
    agent = None

    class VocalApprovalError(ValueError):  # placeholder so error mapping still imports
        code = "TOKEN_INVALID"

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

# Client auth token endpoint
@app.get("/api/auth/token")
@app.post("/api/auth/token")
def get_client_auth_token():
    if not _demo_auth_enabled():
        raise HTTPException(404, "Not found")
    try:
        token = issue_jwt_token()
    except RuntimeError as exc:
        raise HTTPException(503, "Demo authentication is unavailable") from exc
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 86400,
    }

class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
    groove: Optional[Literal["straight", "half_time", "swing", "half_time_shuffle"]] = None
    lyrics_prompt: Optional[str] = None
    lyrics_language: Optional[str] = "en"
    vocal_style: Optional[str] = "soulful_lead"
    vocal_approved: Optional[bool] = False
    vocal_approval_token: Optional[str] = None
    edited_lyrics: Optional[Union[List[str], List[Dict[str, Any]]]] = None
    acknowledge_unassessed_rights: Optional[bool] = False


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
    "vocal": {"vocal_lead"},
    "vocal_lead": {"vocal_lead"},
}

@generation_router.post("/api/generate")
async def generate_riff(req: GenerateRequest, user_id: str = Depends(require_generation)):
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
    has_vocal_context = bool(
        req.lyrics_prompt
        or req.vocal_approved
        or (req.previous_score and "vocal_lead" in (req.previous_score.get("part_scores") or {}))
    )
    unmatched_locks = [
        lock for lock in requested_locks
        if not (
            (lock.lower() in ("vocal", "vocal_lead") and has_vocal_context)
            or any(
                lock.lower() == instrument.lower()
                or lock.lower() in instrument.lower()
                or instrument.lower() in LOCK_ALIASES.get(lock.lower(), set())
                for instrument in instruments
            )
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
            stored_record = get_take(req.base_storage_id, owner_id=user_id)
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
            groove=req.groove,
            lyrics_prompt=req.lyrics_prompt,
            lyrics_language=req.lyrics_language or "en",
            vocal_style=req.vocal_style or "soulful_lead",
            vocal_approved=bool(req.vocal_approved),
            vocal_approval_token=req.vocal_approval_token,
            edited_lyrics=req.edited_lyrics,
            acknowledge_unassessed_rights=bool(req.acknowledge_unassessed_rights),
            storage_owner_id=user_id,
        )
        return {
            "status": "success",
            "data": data
        }
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
    except VocalApprovalError as exc:
        return _vocal_error_response(exc)
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
    except Exception as exc:
        mapped = _vocal_error_response(exc)
        if mapped is not None:
            return mapped
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "code": "GENERATION_ERROR",
                "detail": str(exc)
            }
        )


class VocalApproveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str
    vocal_trace_id: Optional[str] = None
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
    acknowledge_unassessed_rights: Optional[bool] = False


def _vocal_error_response(exc: Exception):
    """Map approval failures to stable codes; None means 'not a vocal approval error'."""
    from riffs_api.token_store import TokenStoreUnavailable
    if isinstance(exc, PromptRefusal):
        return JSONResponse(
            status_code=422,
            content={
                "status": "error",
                "code": exc.code,
                "detail": exc.detail,
                "alternative": exc.alternative,
            },
        )
    if isinstance(exc, VocalApprovalError):
        status = 422 if exc.code == "POTENTIAL_MATCH" else 403
        return JSONResponse(status_code=status, content={"status": "error", "code": exc.code, "detail": str(exc)})
    if isinstance(exc, TokenStoreUnavailable):
        return JSONResponse(status_code=503, content={"status": "error", "code": "VOCAL_REPLAY_STORE_UNAVAILABLE", "detail": str(exc)})
    if isinstance(exc, RuntimeError) and "RIFFS_VOCAL_SECRET" in str(exc):
        return JSONResponse(status_code=503, content={"status": "error", "code": "VOCAL_NOT_CONFIGURED", "detail": "Vocal signing secret is not configured on this server."})
    return None


@generation_router.post("/api/vocals/approve")
async def approve_vocal_track(req: VocalApproveRequest, user_id: str = Depends(require_generation)):
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
            vocal_trace_id=req.vocal_trace_id,
            acknowledge_unassessed_rights=bool(req.acknowledge_unassessed_rights),
            storage_owner_id=user_id,
        )
        return {"status": "success", "data": data}
    except Exception as exc:
        mapped = _vocal_error_response(exc)
        if mapped is not None:
            return mapped
        if isinstance(exc, ValueError):
            return JSONResponse(status_code=403, content={"status": "error", "code": "VOCAL_AUTH_FAILED", "detail": str(exc)})
        return JSONResponse(status_code=500, content={"status": "error", "code": "VOCAL_RENDER_FAILED", "detail": str(exc)})


app.include_router(generation_router)


@app.get("/api/takes/{storage_id}")
def get_stored_take(storage_id: str, user_id: str = Depends(require_generation)):
    """Read a take only when it belongs to the authenticated principal."""
    from riffs_api.take_store import get_take
    record = get_take(storage_id, owner_id=user_id)
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
async def attach_video_endpoint(req: VideoRemuxRequest, user_id: str = Depends(require_generation)):
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


