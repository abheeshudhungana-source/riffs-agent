"""Default API generation, checkpoint context and the actual browser handoff."""
import json
import os
from pathlib import Path
import shutil
import subprocess
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from agent import RiffsAgent, _generate_vocal_melody_events
from app import app, require_generation
from riffs_api.token_store import MemoryTokenStore


@pytest.fixture
def client(tmp_path):
    old_override = app.dependency_overrides.get(require_generation)
    app.dependency_overrides[require_generation] = lambda: "lyrics-flow-test"
    with patch.dict(os.environ, {
        "ANTHROPIC_API_KEY": "", "RIFFS_VOCAL_SECRET": "lyrics-flow-test-secret-at-least-32",
        "RIFFS_TAKE_STORE_PATH": str(tmp_path),
        "RIFFS_AUDIT_LOG_PATH": str(tmp_path / "audit.jsonl"),
    }), patch("agent.get_token_store", return_value=MemoryTokenStore()):
        yield TestClient(app)
    if old_override is None:
        app.dependency_overrides.pop(require_generation, None)
    else:
        app.dependency_overrides[require_generation] = old_override


def approval_request(checkpoint):
    fields = ("prompt", "lyrics_prompt", "lyrics_language", "vocal_style", "key", "bpm",
              "groove", "instruments", "seed")
    return {**{field: checkpoint[field] for field in fields},
            "chords": " - ".join(checkpoint["chords"]),
            "token": checkpoint["vocal_confirmation_token"],
            "edited_lyrics": checkpoint["lyrics_draft"]["bars"],
            "acknowledge_unassessed_rights": True}


@pytest.mark.parametrize("extra", [{}, {"lyrics_prompt": None}, {"lyrics_prompt": "  "}])
def test_default_api_requests_offer_the_new_poetry_draft_before_any_voice(client, extra):
    with patch("agent._generate_vocal_melody_events", wraps=_generate_vocal_melody_events) as voice:
        response = client.post("/api/generate", json={"prompt": "Warm soul by the sea", **extra})
    assert response.status_code == 200, response.text
    checkpoint = response.json()["data"]
    assert checkpoint["status"] == "awaiting_vocal_confirmation"
    assert checkpoint["lyrics_prompt"] == "Warm soul by the sea"
    assert checkpoint["lyrics_draft"]["verse_plan"]["theme"] == checkpoint["lyrics_prompt"]
    assert len(checkpoint["lyrics_draft"]["bars"]) == len(checkpoint["chords"])
    assert all(bar["text"] for bar in checkpoint["lyrics_draft"]["bars"])
    assert checkpoint["vocal_confirmation_token"]
    assert not any(stem["lane"] == "vocal_lead" for stem in checkpoint["stems"])
    voice.assert_not_called()


def test_explicit_prompt_and_normalized_options_round_trip_using_only_checkpoint(client):
    request = {"prompt": "Warm soul groove", "lyrics_prompt": 'Rain, then "a new beginning"',
               "lyrics_language": " ES ", "vocal_style": " POP_LEAD ", "seed": 71}
    response = client.post("/api/generate", json=request)
    assert response.status_code == 200, response.text
    checkpoint = response.json()["data"]
    assert checkpoint["prompt"] == request["prompt"]
    assert checkpoint["lyrics_prompt"] == request["lyrics_prompt"]
    assert checkpoint["lyrics_language"] == "es"
    assert checkpoint["vocal_style"] == "pop_lead"
    with patch("agent.draft_bar_aligned_lyrics", side_effect=AssertionError("regenerated")):
        result = client.post("/api/vocals/approve", json=approval_request(checkpoint))
    assert result.status_code == 200, result.text
    assert result.json()["data"]["lyrics"] == checkpoint["lyrics_draft"]["bars"]


def test_browser_approves_and_renders_real_api_lyrics_and_can_keep_instrumental(client):
    if not shutil.which("node"):
        pytest.skip("Node is required for the real UI handler regression")
    response = client.post("/api/generate", json={"prompt": "Warm soul", "seed": 17})
    assert response.status_code == 200, response.text
    checkpoint = response.json()["data"]
    request = approval_request(checkpoint)
    approved = client.post("/api/vocals/approve", json=request)
    assert approved.status_code == 200, approved.text
    result = subprocess.run(
        ["node", str(Path(__file__).with_name("lyrics_flow_ui.cjs"))],
        input=json.dumps({"checkpoint": checkpoint, "approved": approved.json()["data"]}),
        text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "lyrics flow passed" in result.stdout


def test_ui_styles_are_all_accepted_by_backend(client):
    import re
    html = (Path(__file__).parents[1] / "index.html").read_text()
    select = re.search(r'<select id="select-vocal-style".*?</select>', html, re.S).group()
    styles = re.findall(r'<option value="([^"]+)"', select)
    assert styles
    assert len(styles) == len(set(styles))
    for style in styles:
        response = client.post("/api/generate", json={"prompt": "Warm soul", "vocal_style": style})
        assert response.status_code == 200, (style, response.text)
        assert response.json()["data"]["vocal_style"] == style


def test_locked_approved_vocal_is_preserved_when_no_new_story_is_requested(client):
    checkpoint = client.post("/api/generate", json={"prompt": "Warm soul", "seed": 17}).json()["data"]
    approved = client.post("/api/vocals/approve", json=approval_request(checkpoint)).json()["data"]
    response = client.post("/api/generate", json={
        "prompt": "Warm soul", "seed": 18, "locked_parts": ["vocal_lead"],
        "previous_score": approved["score"],
    })
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] != "awaiting_vocal_confirmation"
    previous = next(lane for lane in approved["score"]["lanes"] if lane["instrument"] == "vocal_lead")
    current = next(lane for lane in data["score"]["lanes"] if lane["instrument"] == "vocal_lead")
    assert previous["hash"] == current["hash"]
