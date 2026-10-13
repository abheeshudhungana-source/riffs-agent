"""Chord-first backend routes mounted by the RIFFs application."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from riffs_api.progression import ProgressionError, parse_progression
from riffs_api.render import render_symbolic_package, symbolic_package_filename
from riffs_api.score import draft_score
from riffs_api.agent_loop import RiffBuildEnvironment, run_loop

router = APIRouter()


class ParseProgressionRequest(BaseModel):
    progression: str = Field(min_length=1, max_length=512, description="Chord symbols or Nashville numbers separated by bars, commas, or dashes.")
    key: str | None = Field(default=None, description="Optional major or minor key, such as 'G major' or 'E minor'. Required for Nashville numbers.")
    tempo_bpm: int = Field(default=120, ge=40, le=240, description="Tempo in beats per minute.")


class ChordResponse(BaseModel):
    bar: int
    source: str
    root: str
    pitch_class: int
    quality: str
    symbol: str
    scale_degree: int | None
    nashville: str | None
    source_kind: str


class ParseProgressionResponse(BaseModel):
    key: str | None
    tempo_bpm: int
    chord_chart: str
    nashville_chart: str | None
    chords: list[ChordResponse]


class ScoreNoteResponse(BaseModel):
    pitch_midi: int
    onset_beats: int
    duration_beats: int
    velocity: int


class ScoreBarResponse(BaseModel):
    bar: int
    chord_symbol: str
    nashville: str | None
    notes: list[ScoreNoteResponse]


class ScoreDraftResponse(BaseModel):
    key: str | None
    tempo_bpm: int
    time_signature: str
    beats_per_bar: int
    chord_chart: str
    nashville_chart: str | None
    bars: list[ScoreBarResponse]


class AgentLoopRequest(BaseModel):
    progression: str = Field(min_length=1, max_length=512)
    key: str | None = Field(default=None, description="Required for Nashville-number progressions.")
    tempo_bpm: int = Field(default=120, ge=40, le=240)
    max_steps: int = Field(default=5, ge=1, le=5)
    prompt: str = Field(default="", max_length=2000, description="Optional creative direction checked against RIFFs guardrails before parsing.")


@router.post("/api/v1/progressions/parse", response_model=ParseProgressionResponse)
def parse_progression_endpoint(request: ParseProgressionRequest) -> ParseProgressionResponse:
    try:
        result = parse_progression(request.progression, request.key)
    except ProgressionError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return ParseProgressionResponse(
        key=result.key,
        tempo_bpm=request.tempo_bpm,
        chord_chart=result.chord_chart,
        nashville_chart=result.nashville_chart,
        chords=[ChordResponse(**chord.__dict__) for chord in result.chords],
    )


@router.post("/api/v1/scores/draft", response_model=ScoreDraftResponse)
def draft_score_endpoint(request: ParseProgressionRequest) -> ScoreDraftResponse:
    try:
        score = draft_score(request.progression, request.key, request.tempo_bpm)
    except ProgressionError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return ScoreDraftResponse(
        key=score.key,
        tempo_bpm=score.tempo_bpm,
        time_signature=score.time_signature,
        beats_per_bar=score.beats_per_bar,
        chord_chart=score.chord_chart,
        nashville_chart=score.nashville_chart,
        bars=[
            ScoreBarResponse(
                bar=bar.bar,
                chord_symbol=bar.chord_symbol,
                nashville=bar.nashville,
                notes=[ScoreNoteResponse(**note.__dict__) for note in bar.notes],
            )
            for bar in score.bars
        ],
    )


@router.post("/api/v1/tools/render-riff-to-audio")
def render_riff_to_audio_endpoint(request: ParseProgressionRequest) -> Response:
    try:
        package = render_symbolic_package(request.progression, request.key, request.tempo_bpm)
    except ProgressionError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return Response(
        content=package,
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{symbolic_package_filename(request.key, request.tempo_bpm)}"'
            )
        },
    )


@router.post("/api/v1/agent/run")
def run_agent_loop_endpoint(request: AgentLoopRequest) -> dict:
    """Run the deterministic observe-decide-act loop for a symbolic riff draft."""
    env = RiffBuildEnvironment(
        request.progression,
        request.key,
        request.tempo_bpm,
        prompt=request.prompt,
    )
    history = run_loop(env, max_steps=request.max_steps)
    final_state = env.get_state()
    return {
        "status": final_state["status"],
        "done": final_state["done"],
        "step_count": len(history),
        "history": history,
        "final_state": final_state,
    }
