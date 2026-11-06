"""Focused checks for planned lyric drafting and the existing approval boundary."""
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from agent import RiffsAgent, VocalApprovalError, draft_bar_aligned_lyrics
from riffs_api.lyrics import assess_verse, english_prosody, generate_verse, plan_verse


CHORDS = ["Am", "F", "C", "G"]
VERSE = [
    "The rain has washed the road tonight",
    "I turn the wheel toward morning light",
    "I leave your letters by the door",
    "My heart can ask for nothing more",
]


def draft(complete=None, **overrides):
    request = dict(chords=CHORDS, prompt="Rain on the road", bpm=110, language="en",
                   vocal_style="soulful_lead", vibe="neosoul", instrumental_style="Warm soul",
                   key="Am", groove="straight", instruments=["bass_guitar"],
                   fallback_lines=VERSE, complete=complete)
    return generate_verse(**{**request, **overrides})


def response(*verses):
    return json.dumps({"candidates": [{"lines": lines} for lines in verses]})


def test_selects_valid_candidate_and_recomputes_alignment_and_syllables():
    complete = Mock(return_value=response(["rain"] * 4, VERSE, ["blank"]))
    result = draft(complete)
    assert [bar["text"] for bar in result["bars"]] == VERSE
    assert [bar["chord"] for bar in result["bars"]] == CHORDS
    assert [bar["bar"] for bar in result["bars"]] == [1, 2, 3, 4]
    assert all(bar["syllables"] == 8 for bar in result["bars"])
    assert result["rhyme_scheme"] == "AABB"
    assert result["candidate_count"] == 2
    assert result["validation"]["issues"] == {}
    complete.assert_called_once()
    assert complete.call_args.args[1]["plan"]["theme"] == "Rain on the road"


def test_repairs_only_failing_lines_and_retains_other_text():
    too_long = "The rain has washed the road and every single letter in the town tonight"
    complete = Mock(side_effect=[response([too_long, *VERSE[1:]]),
                                json.dumps({"replacements": [{"bar": 1, "text": VERSE[0]}]})])
    result = draft(complete)
    assert result["repaired"] is True
    assert [bar["text"] for bar in result["bars"]] == VERSE
    assert complete.call_count == 2
    assert set(complete.call_args.args[1]["issues"]) == {1}


@pytest.mark.parametrize("repair", [
    {"replacements": [{"bar": 2, "text": "An unrequested rewrite"}]},
    {"replacements": [{"bar": 1, "text": "<script>bad</script>"}]},
    {"replacements": [{"bar": 1, "text": "Unpronounceablezzzz"}]},
    {"replacements": [{"bar": True, "text": VERSE[0]}]},
    {"replacements": [{"bar": 1, "text": VERSE[0]}, {"bar": 1, "text": VERSE[0]}]},
])
def test_bad_repairs_keep_original_draft_and_do_not_retry_forever(repair):
    lines = ["The rain has washed the road and every single letter in the town tonight", *VERSE[1:]]
    complete = Mock(side_effect=[response(lines), json.dumps(repair)])
    result = draft(complete)
    assert not result["repaired"]
    assert [bar["text"] for bar in result["bars"]] == lines
    assert result["validation"]["issues"]
    assert complete.call_count == 2


@pytest.mark.parametrize("raw", ["not json", "null", '{"candidates": null}', response([" "] * 4),
                                 response(["<script>bad</script>"] * 4), response(VERSE + ["extra"]),
                                 response(["<b>not plain text</b>"] * 4),
                                 response(["first line\nsecond line"] * 4)])
def test_invalid_model_output_uses_labelled_fallback(raw):
    complete = Mock(return_value=raw)
    result = draft(complete)
    assert result["generation_source"] == "template_fallback"
    assert len(result["bars"]) == 4
    assert all(bar["text"] for bar in result["bars"])
    complete.assert_called_once()


def test_phonetics_handle_silent_letters_unknowns_and_false_rhymes():
    assert english_prosody("queue", 8)["syllables"] == 1
    assert english_prosody("zzzoovian", 8)["syllables"] is None
    assert english_prosody("123", 8)["syllables"] is None
    # Similar spelling does not make love and move rhyme.
    assessment = assess_verse(["I love", "I move"], plan_verse("love", 2, 110, "en"))
    assert assessment["rhyme_pairs"][0]["status"] == "mismatch"


@pytest.mark.parametrize("language,lines", [("es", ["Luz en la ciudad"] * 4),
                                          ("ja", ["夜の街を歩く"] * 4)])
def test_other_languages_do_not_claim_english_prosody_or_verified_rhymes(language, lines):
    result = draft(Mock(return_value=response(lines)), language=language)
    assert result["language"] == language
    assert result["rhyme_scheme"] is None
    assert result["validation"]["prosody_status"] == "unassessed"
    assert all(bar["syllables"] is None for bar in result["bars"])


@pytest.mark.parametrize("count", [2, 4, 8, 16])
def test_local_fallback_develops_topic_without_repeating_four_lines(count):
    result = draft(chords=(CHORDS * 4)[:count])
    texts = [bar["text"] for bar in result["bars"]]
    assert len(set(texts)) == count
    assert "road" in " ".join(texts)
    assert result["verse_plan"]["bars"][-1]["purpose"] == "resolve with an image"
    assert result["generation_source"] == "template_fallback"


def test_provider_failure_falls_back_and_preserves_public_draft_interface():
    with patch("litellm.completion", side_effect=TimeoutError("offline")) as complete:
        result = draft_bar_aligned_lyrics(CHORDS, "Am", 110, "Rain on the road", api_key="test")
    assert result["generation_source"] == "template_fallback"
    assert len(result["bars"]) == 4
    assert complete.call_args.kwargs["num_retries"] == 0
    assert complete.call_args.kwargs["timeout"] == 20


def test_provider_receives_plan_as_data_and_draft_metadata_cannot_override_chords():
    model_response = type("Response", (), {"choices": [
        type("Choice", (), {"message": type("Message", (), {"content": response(VERSE)})()})()
    ]})()
    with patch("litellm.completion", return_value=model_response) as complete:
        result = draft_bar_aligned_lyrics(CHORDS, "Am", 110, "Rain on the road", api_key="test")
    assert result["generation_source"] == "model"
    assert [bar["chord"] for bar in result["bars"]] == CHORDS
    messages = complete.call_args.kwargs["messages"]
    assert "Rain on the road" not in messages[0]["content"]
    assert json.loads(messages[1]["content"])["plan"]["theme"] == "Rain on the road"


def test_approval_does_not_regenerate_poetry_and_requires_exact_reviewed_text():
    with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
        "ANTHROPIC_API_KEY": "", "RIFFS_VOCAL_SECRET": "test-lyrics-approval-secret-32-chars",
        "RIFFS_TAKE_STORE_PATH": directory,
        "RIFFS_AUDIT_LOG_PATH": str(Path(directory) / "audit.jsonl"),
    }):
        agent = RiffsAgent()
        request = dict(prompt="Warm soul", chords=" - ".join(CHORDS),
                       lyrics_prompt="Rain on the road", seed=17)
        with patch("agent._generate_vocal_melody_events", side_effect=AssertionError("too early")):
            checkpoint = agent.generate(**request)
        assert checkpoint["status"] == "awaiting_vocal_confirmation"
        assert checkpoint["lyrics_draft"]["verse_plan"]["theme"] == request["lyrics_prompt"]
        assert not any(stem["lane"] == "vocal_lead" for stem in checkpoint["stems"])
        approved_lines = checkpoint["lyrics_draft"]["bars"]
        changed = [dict(bar) for bar in approved_lines]
        changed[0]["text"] = "An altered line"
        with patch("agent.draft_bar_aligned_lyrics", side_effect=AssertionError("regenerated")):
            with pytest.raises(VocalApprovalError) as error:
                agent.generate(**request, vocal_approved=True, edited_lyrics=changed,
                               vocal_approval_token=checkpoint["vocal_confirmation_token"],
                               acknowledge_unassessed_rights=True)
            assert error.value.code == "LYRICS_MISMATCH"
            approved = agent.generate(**request, vocal_approved=True, edited_lyrics=approved_lines,
                                      vocal_approval_token=checkpoint["vocal_confirmation_token"],
                                      acknowledge_unassessed_rights=True)
        assert approved["lyrics"] == approved_lines
        assert len(approved["lyrics"]) == len(CHORDS)
        assert any(stem["lane"] == "vocal_lead" for stem in approved["stems"])
