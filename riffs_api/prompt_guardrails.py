"""Deterministic ingress checks for RIFFs' instrumental and originality boundaries."""

from __future__ import annotations

import re


class PromptRefusal(ValueError):
    """A user request that falls outside the product's declared scope."""

    def __init__(self, code: str, detail: str, alternative: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.alternative = alternative


_LYRICS_OR_VOCALS = re.compile(
    r"\b(?:write|add|generate|include|compose|provide)\b.{0,48}"
    r"(?P<negation>no|without)\s+(?P<content>lyrics?|vocals?)\b"
    r"|\b(?:write|add|generate|include|compose|provide)\b.{0,48}\b(?P<content_direct>lyrics?|vocals?)\b",
    re.IGNORECASE,
)
_FULL_SONG = re.compile(
    r"\b(?P<negation>no|not|without)\s+(?:(?:a|the)\s+)?"
    r"(?P<negative_target>(?:full|entire|complete)\s+(?:original\s+)?song)\b"
    r"|\b(?P<target>(?:full|entire|complete)\s+(?:original\s+)?song)\b",
    re.IGNORECASE,
)
_COPY_INTENT = re.compile(
    r"\b(?:copy|make|create|imitate|recreate|replicate|reproduce|clone|transcribe|play|generate)\b",
    re.IGNORECASE,
)
_EXACTNESS = re.compile(
    r"\b(?:note\s*[- ]\s*for\s*[- ]\s*note|verbatim|exact(?:ly)?|identical(?:ly)?)\b",
    re.IGNORECASE,
)
_SONG_REFERENCE = re.compile(r"\b(?:song|track|recording|commercial hit|single|title)\b", re.IGNORECASE)
_TITLE_LIKE_TEXT = re.compile(
    r"\b[A-Z][a-zA-Z']+(?:\s+(?:[A-Z][a-zA-Z']+|to|of|and|the|in|for)){1,5}\b"
    r"|\b[A-Z][a-zA-Z']{3,}\b"
)
_GENERIC_REFERENTS = {"my", "your", "our", "this", "that", "own", "original", "a", "an", "the"}


def _is_explicit_exact_copy(prompt: str) -> bool:
    """Require copy intent + exactness + a named or explicitly musical target."""
    intent_matches = list(_COPY_INTENT.finditer(prompt))
    exact_matches = list(_EXACTNESS.finditer(prompt))
    for intent in intent_matches:
        for exact in exact_matches:
            if intent.start() < exact.start() and exact.start() - intent.end() <= 120:
                target = prompt[intent.end():exact.start()]
            elif exact.start() < intent.start() and intent.start() - exact.end() <= 80:
                target = prompt[exact.end():intent.start()]
            else:
                continue
            if _SONG_REFERENCE.search(target):
                return True
            for match in _TITLE_LIKE_TEXT.finditer(target):
                first_word = match.group(0).split()[0].lower()
                if first_word not in _GENERIC_REFERENTS:
                    return True
    return False


def validate_prompt(prompt: str) -> None:
    """Raise before generation for requests outside RIFFs' documented scope."""
    prompt = prompt or ""
    lyric_match = _LYRICS_OR_VOCALS.search(prompt)
    if lyric_match and lyric_match.group("negation") is None:
        raise PromptRefusal(
            "INSTRUMENTAL_ONLY",
            "RIFFs creates instrumental accompaniment and does not generate lyrics or vocals.",
            "Try describing the instruments, groove, or mood you want instead.",
        )
    full_song_match = _FULL_SONG.search(prompt)
    if full_song_match and full_song_match.group("target") is not None:
        raise PromptRefusal(
            "LOOP_LENGTH_LIMIT",
            "RIFFs is designed to create short practice and sketching loops, not complete songs.",
            "Ask for an original 4-to-16-bar instrumental loop instead.",
        )
    if _is_explicit_exact_copy(prompt):
        raise PromptRefusal(
            "COPYRIGHT_REPRODUCTION_REQUEST",
            "RIFFs can’t reproduce a named song or recording note-for-note, verbatim, or exactly.",
            "Try asking for an original riff with a broad genre, mood, or groove description.",
        )
