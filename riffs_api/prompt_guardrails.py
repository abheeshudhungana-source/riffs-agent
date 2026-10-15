"""Deterministic ingress checks for RIFFs' instrumental, originality, and safety boundaries."""

from __future__ import annotations

import re
from typing import Any, List, Dict, Union


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
    r"(?P<negative_target>(?:full|entire|complete)\s+(?:[\w-]+\s+){0,3}(?:song|track))\b"
    r"|\b(?P<target>(?:full|entire|complete)\s+(?:[\w-]+\s+){0,3}(?:song|track))\b",
    re.IGNORECASE,
)
_COPY_INTENT = re.compile(
    r"\b(?:copy|make|create|imitate|recreate|replicate|reproduce|clone|transcribe|play|generate|write|sing|recite|give|provide)\b",
    re.IGNORECASE,
)
_EXACTNESS = re.compile(
    r"\b(?:note\s*[- ]\s*for\s*[- ]\s*note|verbatim|exact(?:ly)?|identical(?:ly)?)\b",
    re.IGNORECASE,
)
_SONG_REFERENCE = re.compile(
    r"\b(?:song|track|recording|commercial hit|single|title|lyrics?|verse|chorus|words)\b",
    re.IGNORECASE,
)
_TITLE_LIKE_TEXT = re.compile(
    r"\b[A-Z][a-zA-Z']+(?:\s+(?:[A-Z][a-zA-Z']+|to|of|and|the|in|for)){1,5}\b"
    r"|\b[A-Z][a-zA-Z']{3,}\b"
)
_GENERIC_REFERENTS = {"my", "your", "our", "this", "that", "own", "original", "a", "an", "the"}

_FAMOUS_VERBATIM_LYRIC_FRAGMENTS = re.compile(
    r"\b(?:scaramouche|galileo|thunderbolt\s+and\s+lightning|"
    r"is\s+this\s+the\s+real\s+life|mama,\s+just\s+killed\s+a\s+man|"
    r"we\s+will\s+rock\s+you|we\s+are\s+the\s+champions)\b",
    re.IGNORECASE,
)

# Well-known verbatim copyrighted lyrics / song references
_FAMOUS_VERBATIM_LYRICS = re.compile(
    r"\b(?:bohemian\s+rhapsody|scaramouche|galileo|thunderbolt\s+and\s+lightning|"
    r"is\s+this\s+the\s+real\s+life|mama,\s+just\s+killed\s+a\s+man|we\s+will\s+rock\s+you|"
    r"we\s+are\s+the\s+champions|hotel\s+california|billie\s+jean|smells\s+like\s+teen\s+spirit|"
    r"sweet\s+child\s+o'?\s*mine|stairway\s+to\s+heaven)\b",
    re.IGNORECASE,
)

# HTML / Script injection patterns
_XSS_INJECTION = re.compile(
    r"<\s*script\b[^>]*>|<\s*/\s*script\s*>|javascript:\s*|<\s*svg\b|<\s*img\b[^>]+onerror|<\s*iframe\b",
    re.IGNORECASE,
)

# Harmful / violent language patterns
_VIOLENCE_HARM = re.compile(
    r"\b(?:kill\s+them\s+all|kill\s+all\s+(?:the|of\s+the)\b|murder\s+them|slaughter\s+everyone|die\s+all)\b",
    re.IGNORECASE,
)


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


def validate_prompt(prompt: str, allow_lyrics: bool = False) -> None:
    """Raise before generation for requests outside RIFFs' documented scope."""
    prompt = prompt or ""

    if _XSS_INJECTION.search(prompt):
        raise PromptRefusal(
            "INJECTION_DETECTED",
            "HTML or script injection characters are not permitted.",
            "Describe the musical direction using plain text.",
        )

    if _VIOLENCE_HARM.search(prompt):
        raise PromptRefusal(
            "SAFETY_VIOLATION",
            "Prompts containing harmful or violent instructions are refused.",
            "Use positive or descriptive creative imagery instead.",
        )

    if _FAMOUS_VERBATIM_LYRIC_FRAGMENTS.search(prompt) or (
        _FAMOUS_VERBATIM_LYRICS.search(prompt) and (_EXACTNESS.search(prompt) or _COPY_INTENT.search(prompt))
    ):
        raise PromptRefusal(
            "COPYRIGHT_REPRODUCTION_REQUEST",
            "RIFFs cannot reproduce famous commercial song lyrics verbatim.",
            "Ask for an original lyric theme or mood description instead.",
        )

    lyric_match = _LYRICS_OR_VOCALS.search(prompt)
    if not allow_lyrics and lyric_match and lyric_match.group("negation") is None:
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


def validate_lyrics(lyrics: Any) -> List[str]:
    """Validate and sanitize draft or edited lyrics lines."""
    if lyrics is None:
        raise PromptRefusal(
            "INVALID_LYRICS",
            "Lyrics input is required.",
            "Provide a 4-line verse.",
        )

    if not isinstance(lyrics, list) or len(lyrics) == 0:
        raise PromptRefusal(
            "INVALID_LYRICS",
            "Lyrics must be a non-empty list of lines.",
            "Provide a 4-line verse with one string per line.",
        )

    # Convert items to plain string lines while validating types
    clean_lines: List[str] = []
    total_length = 0

    for idx, item in enumerate(lyrics):
        text_val = None
        if isinstance(item, str):
            text_val = item
        elif isinstance(item, dict):
            # Dict item must contain a non-empty string under 'text' or 'lyric'
            candidate = item.get("text") if "text" in item else item.get("lyric")
            if not isinstance(candidate, str):
                raise PromptRefusal(
                    "INVALID_LYRICS",
                    f"Line {idx + 1} lyric text must be a string, got {type(candidate).__name__}.",
                    "Provide text strings for each lyric line.",
                )
            text_val = candidate
        else:
            raise PromptRefusal(
                "INVALID_LYRICS",
                f"Line {idx + 1} must be a string or dict with 'text', got {type(item).__name__}.",
                "Provide text strings for each lyric line.",
            )

        trimmed = text_val.strip()
        if not trimmed:
            raise PromptRefusal(
                "INVALID_LYRICS",
                f"Line {idx + 1} cannot be blank or empty.",
                "Provide lyrical text for each bar.",
            )

        if len(trimmed) > 250:
            raise PromptRefusal(
                "LENGTH_LIMIT",
                f"Line {idx + 1} exceeds maximum length of 250 characters.",
                "Keep lyrics concise to fit a 4-bar practice loop.",
            )

        total_length += len(trimmed)
        if total_length > 1000:
            raise PromptRefusal(
                "LENGTH_LIMIT",
                "Total lyrics length exceeds 1000 characters limit.",
                "Keep lyrics concise to fit a 4-line verse.",
            )

        if _XSS_INJECTION.search(trimmed):
            raise PromptRefusal(
                "INJECTION_DETECTED",
                "HTML or script tags detected in lyrics.",
                "Use plain text for lyrics without HTML or script code.",
            )

        if _VIOLENCE_HARM.search(trimmed):
            raise PromptRefusal(
                "SAFETY_VIOLATION",
                "Lyrics containing harmful or violent language are refused.",
                "Use non-violent creative expressions.",
            )

        if _FAMOUS_VERBATIM_LYRICS.search(trimmed):
            raise PromptRefusal(
                "COPYRIGHT_REPRODUCTION_REQUEST",
                "Lyrics appear to be a verbatim excerpt of a known commercial song.",
                "Write original lyrics matching the vibe of the accompaniment.",
            )

        clean_lines.append(trimmed)

    if len(clean_lines) < 4:
        raise PromptRefusal(
            "INVALID_LYRICS",
            f"Verse must have at least 4 lines (got {len(clean_lines)}).",
            "Provide a complete 4-line verse.",
        )

    return clean_lines
