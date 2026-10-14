"""RIFFs symbolic composer.

"The notes come first": this module turns a chord progression, a key, a style
prompt and a seed into a *symbolic score* - note events per instrument lane.
The browser then renders that score to sound. Nothing here touches audio.

Design rules (see docs/PRD.md section 3.6):
  * Events are expressed in beats, not seconds. Tempo is a session-level
    property, so a lane's notes never depend on BPM.
  * The seed changes phrasing on unlocked lanes (template choice, ghost notes,
    melodic contour, velocity). The same seed always yields the same notes.
  * A locked lane is copied verbatim from the previous score. It never goes
    through the generator, so its notes cannot drift between takes.
"""

import hashlib
import random
import re
from typing import Any, Dict, List, Optional, Tuple

BEATS_PER_BAR = 4
MAX_EVENTS_PER_LANE = 2000

PITCH_CLASS = {
    "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5,
    "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11,
}
MAJOR_SCALE = [0, 2, 4, 5, 7, 9, 11]
MINOR_SCALE = [0, 2, 3, 5, 7, 8, 10]

# Instrument id -> sound tier (one instrument per tier, max 3 per take).
INSTRUMENT_TIER = {
    "bass_guitar": "low", "contrabass": "low", "bass_drums": "low", "floor_tom": "low",
    "rhythm_guitar": "mid", "acoustic_piano": "mid", "tenor_sax": "mid", "bongos": "mid",
    "cymbals": "high", "ukulele": "high", "piccolo": "high", "triangle": "high", "drum_kit": "high",
}
# The UI lock buttons talk about lanes (bass / lead / drums); map them to tiers.
LANE_ALIAS = {"bass": "low", "lead": "mid", "drums": "high"}


# --------------------------------------------------------------------------
# Chord parsing
# --------------------------------------------------------------------------
_CHORD_RE = re.compile(r"^([A-G][#b]?)(.*?)(?:/([A-G][#b]?))?$")
_NASHVILLE_RE = re.compile(r"^([b#]?)([1-7])(.*?)(?:/([b#]?[1-7]))?$")


_ROMAN_MAP = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7}
_ROMAN_RE = re.compile(r"^([b#]?)(VII|VI|IV|V|III|II|I)(.*?)(?:/([b#]?(?:VII|VI|IV|V|III|II|I|[1-7])))?$", re.IGNORECASE)


def parse_key(key: Optional[str]) -> Tuple[int, bool]:
    """Return (tonic pitch class, is_minor) for keys like 'Am', 'C', 'F#m', 'C major'."""
    key = (key or "Am").strip()
    parts = key.split()
    root_part = parts[0]
    minor = (
        (len(parts) > 1 and "min" in parts[1].lower())
        or (root_part.endswith("m") and not root_part.lower().endswith("maj"))
    )
    clean_root = root_part[:-1] if (root_part.endswith("m") and not root_part.lower().endswith("maj")) else root_part
    return PITCH_CLASS.get(clean_root, 9 if minor else 0), minor


def quality_to_intervals(quality: str) -> List[int]:
    """Chord-quality suffix -> semitone offsets from the root."""
    q = (quality or "").strip()
    ql = q.lower()
    if ql.startswith("dim"):
        intervals = [0, 3, 6]
        if "7" in ql:
            intervals.append(9)
        return intervals
    if ql.startswith("aug"):
        return [0, 4, 8]
    if ql.startswith("sus2"):
        return [0, 2, 7]
    if ql.startswith("sus"):
        return [0, 5, 7]
    minor = (ql.startswith("m") and not ql.startswith("maj")) or ql.startswith("min")
    intervals = [0, 3, 7] if minor else [0, 4, 7]
    if "maj7" in ql or "maj9" in ql:
        intervals.append(11)
        if "maj9" in ql:
            intervals.append(14)
    elif "7" in ql or re.search(r"(?<!add)9", ql) or "11" in ql or "13" in ql:
        intervals.append(10)
        if re.search(r"(?<!add)9", ql):
            intervals.append(14)
    elif "6" in ql:
        intervals.append(9)
    if "add9" in ql:
        intervals.append(14)
    return intervals


def parse_chord(token: str, key: Optional[str]) -> Dict[str, Any]:
    """Parse a chord name ('Am7', 'C/G'), Nashville number ('b6', '1m'), or Roman numeral ('I', 'vi')."""
    tonic, _minor = parse_key(key)
    token = (token or "").strip()
    nash = _NASHVILLE_RE.match(token)
    if nash:
        accidental, degree, quality, bass = nash.groups()
        offset = MAJOR_SCALE[int(degree) - 1] + (-1 if accidental == "b" else 1 if accidental == "#" else 0)
        root_pc = (tonic + offset) % 12
        bass_pc = None
        if bass:
            b_acc = -1 if bass.startswith("b") else 1 if bass.startswith("#") else 0
            bass_pc = (tonic + MAJOR_SCALE[int(bass[-1]) - 1] + b_acc) % 12
        return {"symbol": token, "root_pc": root_pc, "intervals": quality_to_intervals(quality), "bass_pc": bass_pc}
    roman = _ROMAN_RE.match(token)
    if roman:
        accidental, r_deg, quality, bass = roman.groups()
        degree = _ROMAN_MAP[r_deg.upper()]
        if r_deg.islower() and not quality:
            quality = "m"
        offset = MAJOR_SCALE[degree - 1] + (-1 if accidental == "b" else 1 if accidental == "#" else 0)
        root_pc = (tonic + offset) % 12
        bass_pc = None
        if bass:
            b_acc = -1 if bass.startswith("b") else 1 if bass.startswith("#") else 0
            b_clean = bass.lstrip("b#")
            b_deg = _ROMAN_MAP.get(b_clean.upper(), int(b_clean[-1]) if b_clean[-1].isdigit() else 1)
            bass_pc = (tonic + MAJOR_SCALE[b_deg - 1] + b_acc) % 12
        return {"symbol": token, "root_pc": root_pc, "intervals": quality_to_intervals(quality), "bass_pc": bass_pc}
    match = _CHORD_RE.match(token)
    if not match or match.group(1) not in PITCH_CLASS:
        raise ValueError("Unrecognized chord: `%s`" % token)
    root, quality, bass = match.groups()
    return {
        "symbol": token,
        "root_pc": PITCH_CLASS[root],
        "intervals": quality_to_intervals(quality),
        "bass_pc": PITCH_CLASS[bass] if bass in PITCH_CLASS else None,
    }


# --------------------------------------------------------------------------
# Feel (derived from the style prompt / genre chips)
# --------------------------------------------------------------------------
_PRESETS = {
    "neo": {"swing": 0.45, "vel_scale": 0.92, "bass": ["sync", "root_five", "half"],
            "comp": ["offbeat", "sync", "halfs"], "cym": "ride_swing", "kick": ["sync", "half"]},
    "shuffle": {"swing": 1.0, "vel_scale": 0.95, "bass": ["half", "root_five", "sync"],
                "comp": ["shuffle", "halfs", "offbeat"], "cym": "ride_swing", "kick": ["half", "sync"]},
    "rock": {"swing": 0.0, "vel_scale": 1.05, "bass": ["rock8", "root_five", "rock8"],
             "comp": ["straight8", "straight8", "halfs"], "cym": "hat8", "kick": ["four", "sync"]},
    "lofi": {"swing": 0.35, "vel_scale": 0.82, "bass": ["half", "sync", "pedal"],
             "comp": ["whole", "offbeat", "halfs"], "cym": "ride_quarters", "kick": ["half", "sync"]},
    "funk": {"swing": 0.20, "vel_scale": 1.05, "bass": ["slap", "sync", "octave"],
             "comp": ["funk16", "sync", "offbeat"], "cym": "funk_cym", "kick": ["funk_kick", "sync"]},
    "jazz": {"swing": 0.65, "vel_scale": 0.90, "bass": ["walk", "walk", "root_five"],
             "comp": ["offbeat", "sync", "halfs"], "cym": "ride_swing", "kick": ["half", "sync"]},
    "bossa": {"swing": 0.05, "vel_scale": 0.88, "bass": ["bossa", "half", "root_five"],
              "comp": ["bossa_comp", "offbeat", "halfs"], "cym": "bossa_cym", "kick": ["bossa_kick", "half"]},
    "latin": {"swing": 0.05, "vel_scale": 0.92, "bass": ["bossa", "sync", "octave"],
              "comp": ["bossa_comp", "sync", "funk16"], "cym": "bossa_cym", "kick": ["bossa_kick", "sync"]},
    "reggae": {"swing": 0.35, "vel_scale": 0.95, "bass": ["reggae", "half", "pedal"],
               "comp": ["reggae_skank", "offbeat", "halfs"], "cym": "one_drop", "kick": ["one_drop_kick", "half"]},
    "dub": {"swing": 0.35, "vel_scale": 0.90, "bass": ["reggae", "pedal", "half"],
            "comp": ["reggae_skank", "whole"], "cym": "one_drop", "kick": ["one_drop_kick", "half"]},
    "blues": {"swing": 0.85, "vel_scale": 0.98, "bass": ["walk", "root_five", "half"],
              "comp": ["shuffle", "offbeat", "halfs"], "cym": "ride_swing", "kick": ["half", "sync"]},
    "ballad": {"swing": 0.0, "vel_scale": 0.82, "bass": ["half", "pedal", "root_five"],
               "comp": ["arpeggio", "whole", "halfs"], "cym": "ride_quarters", "kick": ["half", "sync"]},
    "pop": {"swing": 0.0, "vel_scale": 0.98, "bass": ["rock8", "root_five", "sync"],
            "comp": ["straight8", "sync", "halfs"], "cym": "hat8", "kick": ["four", "sync"]},
    "disco": {"swing": 0.0, "vel_scale": 1.05, "bass": ["octave", "rock8", "sync"],
              "comp": ["offbeat", "funk16", "straight8"], "cym": "hat8", "kick": ["four", "sync"]},
    "metal": {"swing": 0.0, "vel_scale": 1.15, "bass": ["rock8", "rock8", "sync"],
              "comp": ["straight8", "straight8", "halfs"], "cym": "hat8", "kick": ["four", "sync"]},
}
_DEFAULT_FEEL = {"swing": 0.15, "vel_scale": 1.0, "bass": ["root_five", "sync", "half"],
                 "comp": ["straight8", "sync", "offbeat"], "cym": "hat8", "kick": ["four", "sync"]}


def parse_feel(prompt: Optional[str]) -> Dict[str, Any]:
    text = (prompt or "").lower()
    feel = dict(_DEFAULT_FEEL)
    tags: List[str] = []
    if "funk" in text or "slap" in text:
        feel.update(_PRESETS["funk"]); tags.append("funk")
    elif "jazz" in text or "bebop" in text or "swing" in text:
        feel.update(_PRESETS["jazz"]); tags.append("jazz")
    elif "bossa" in text or "samba" in text:
        feel.update(_PRESETS["bossa"]); tags.extend(["bossa", "bossa-nova"])
    elif "latin" in text:
        feel.update(_PRESETS["latin"]); tags.append("latin")
    elif "reggae" in text or "one drop" in text or "skank" in text:
        feel.update(_PRESETS["reggae"]); tags.append("reggae")
    elif "dub" in text:
        feel.update(_PRESETS["dub"]); tags.append("dub")
    elif "blues" in text:
        feel.update(_PRESETS["blues"]); tags.append("blues")
    elif "ballad" in text or "ambient" in text:
        feel.update(_PRESETS["ballad"]); tags.append("ballad")
    elif "disco" in text or "dance" in text:
        feel.update(_PRESETS["disco"]); tags.append("disco")
    elif "metal" in text or "heavy" in text:
        feel.update(_PRESETS["metal"]); tags.append("metal")
    elif "neo" in text or "soul" in text:
        feel.update(_PRESETS["neo"]); tags.append("neo-soul")
    elif "shuffle" in text or "halftime" in text:
        feel.update(_PRESETS["shuffle"]); tags.append("halftime-shuffle")
    elif "rock" in text or "indie" in text:
        feel.update(_PRESETS["rock"]); tags.append("indie-rock")
    elif "lo-fi" in text or "lofi" in text or "lo fi" in text:
        feel.update(_PRESETS["lofi"]); tags.append("lo-fi")
    elif "pop" in text:
        feel.update(_PRESETS["pop"]); tags.append("pop")

    if "walking" in text:
        feel["bass"] = ["walk", "walk", "root_five"]
        tags.append("walking-bass")
    if "pocket" in text and "pocket" not in tags:
        feel["swing"] = max(feel.get("swing", 0), 0.25)
        tags.append("pocket")

    feel["tags"] = tags
    return feel


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
def _clamp_vel(vel: float) -> int:
    return max(1, min(127, int(round(vel))))


def _swing_pos(pos: float, swing: float) -> float:
    """Push off-beat eighths late: swing 0 = straight, 1 = triplet."""
    if abs((pos % 1.0) - 0.5) < 1e-9:
        return int(pos) + 0.5 + swing / 6.0
    return pos


def _event(bar: int, pos: float, dur: float, midi: int, vel: float, vel_scale: float, rng: random.Random, jitter: int = 5) -> Dict[str, Any]:
    v = _clamp_vel(vel * vel_scale + rng.randint(-jitter, jitter))
    return {"beat": round(bar * BEATS_PER_BAR + pos, 4), "dur": round(dur, 4), "midi": int(midi), "vel": v}


def _lowest_at_or_above(pc: int, floor_midi: int) -> int:
    return floor_midi + ((pc - floor_midi) % 12)


def _bars_to_chords(chords: List[Dict[str, Any]], loop_bars: int) -> List[Dict[str, Any]]:
    n = len(chords)
    return [chords[min(n - 1, (bar * n) // loop_bars)] for bar in range(loop_bars)]


def _chord_tones(chord: Dict[str, Any]) -> List[int]:
    return [(chord["root_pc"] + i) % 12 for i in chord["intervals"]]


def _closest_voicing(tones: List[int], low: int, high: int, target: float, max_notes: int) -> List[int]:
    if len(tones) > max_notes:  # drop the fifth first, then the top extension
        tones = [t for idx, t in enumerate(tones) if idx != 2] if len(tones) > max_notes else tones
        tones = tones[:max_notes]
    best: Optional[List[int]] = None
    best_dist = 1e9
    for k in range(len(tones)):
        rotated = tones[k:] + tones[:k]
        notes = [_lowest_at_or_above(rotated[0], low)]
        for pc in rotated[1:]:
            notes.append(notes[-1] + 1 + ((pc - notes[-1] - 1) % 12))
        while max(notes) > high and min(notes) - 12 >= low - 4:
            notes = [n - 12 for n in notes]
        dist = abs(sum(notes) / float(len(notes)) - target)
        if dist < best_dist:
            best, best_dist = notes, dist
    return best or []


# --------------------------------------------------------------------------
# Lane generators
# --------------------------------------------------------------------------
_BASS_TEMPLATES = {
    "root_five": [(0, 1.5, "r", 100), (1.5, 0.5, "r", 78), (2, 1.5, "5", 92), (3.5, 0.5, "a", 76)],
    "sync": [(0, 0.75, "r", 100), (1.5, 0.5, "r", 76), (2.5, 0.75, "5", 90), (3.25, 0.5, "a", 74)],
    "walk": [(0, 1, "r", 98), (1, 1, "3", 84), (2, 1, "5", 88), (3, 1, "a", 86)],
    "rock8": [(i * 0.5, 0.5, "r", 98 if i % 2 == 0 else 80) for i in range(8)],
    "half": [(0, 2.5, "r", 100), (3, 0.5, "5", 78), (3.5, 0.5, "a", 74)],
    "pedal": [(0, 3.5, "r", 96), (3.5, 0.5, "a", 70)],
    "slap": [(0, 0.75, "r", 108), (0.75, 0.5, "r", 82), (1.5, 0.5, "5", 98), (2.0, 0.75, "r", 104), (2.75, 0.5, "3", 90), (3.5, 0.5, "a", 84)],
    "bossa": [(0, 1.5, "r", 96), (1.5, 0.5, "5", 86), (2.0, 1.0, "r", 92), (3.0, 1.0, "5", 88)],
    "reggae": [(1.0, 1.0, "r", 104), (2.5, 0.5, "r", 88), (3.0, 1.0, "5", 96)],
    "octave": [(0, 0.5, "r", 98), (0.5, 0.5, "r", 84), (1.0, 0.5, "5", 94), (1.5, 0.5, "5", 82), (2.0, 0.5, "r", 98), (2.5, 0.5, "r", 84), (3.0, 0.5, "5", 94), (3.5, 0.5, "a", 88)],
}


def _pick(pool: List[str], rng: random.Random) -> str:
    # The first entry is the signature groove; the others are variations.
    roll = rng.random()
    if roll < 0.6 or len(pool) == 1:
        return pool[0]
    return pool[1] if roll < 0.85 or len(pool) == 2 else pool[2]


def _gen_bass(inst: str, bars: List[Dict[str, Any]], feel: Dict[str, Any], rng: random.Random) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    pool = feel["bass"] if inst == "bass_guitar" else ["walk"] + feel["bass"]
    for bar, chord in enumerate(bars):
        nxt = bars[(bar + 1) % len(bars)]
        root = _lowest_at_or_above(chord["bass_pc"] if chord.get("bass_pc") is not None else chord["root_pc"], 31)
        next_root = _lowest_at_or_above(nxt["root_pc"], 31)
        third = chord["intervals"][1] if len(chord["intervals"]) > 1 else 4
        approach = next_root - 1 if rng.random() < 0.6 else next_root + 1
        offsets = {"r": 0, "5": 7, "3": third, "a": None}
        for pos, dur, kind, vel in _BASS_TEMPLATES[_pick(pool, rng)]:
            midi = approach if kind == "a" else root + offsets[kind]
            while midi > 47:
                midi -= 12
            while midi < 28:
                midi += 12
            if inst == "contrabass":
                dur = min(dur * 1.2, 3.8)
            events.append(_event(bar, _swing_pos(pos, feel["swing"]), dur, midi, vel, feel["vel_scale"], rng))
        if rng.random() < 0.18:  # ghost note
            events.append(_event(bar, _swing_pos(2.5, feel["swing"]), 0.25, root + 12, 52, feel["vel_scale"], rng, 4))
    events.sort(key=lambda e: (e["beat"], e["midi"]))
    return events


_COMP_TEMPLATES = {
    "straight8": [(0, .5, 96), (.5, .5, 62), (1, .5, 86), (1.5, .5, 60), (2, .5, 92), (2.5, .5, 62), (3, .5, 84), (3.5, .5, 60)],
    "sync": [(0, 1.5, 94), (1.5, 1, 82), (2.5, .5, 70), (3, 1, 86)],
    "offbeat": [(0, .5, 90), (1.5, .5, 84), (2.5, .5, 84), (3.5, .5, 76)],
    "whole": [(0, 4, 88)],
    "halfs": [(0, 2, 92), (2, 2, 84)],
    "shuffle": [(0, .5, 94), (.5, .5, 58), (1, .5, 84), (2, .5, 92), (2.5, .5, 58), (3, .5, 84)],
    "funk16": [(0, .25, 96), (.5, .25, 82), (.75, .5, 90), (1.5, .25, 88), (2, .5, 94), (2.75, .5, 84), (3.5, .5, 90)],
    "reggae_skank": [(1, .5, 94), (1.5, .5, 76), (3, .5, 96), (3.5, .5, 78)],
    "bossa_comp": [(0, .75, 90), (1, .5, 82), (1.75, .75, 88), (2.75, .5, 86), (3.5, .5, 82)],
    "arpeggio": [(0, 1, 90), (1, 1, 84), (2, 1, 88), (3, 1, 82)],
}
_COMP_RANGE = {"rhythm_guitar": (52, 72, 5), "acoustic_piano": (55, 74, 4), "ukulele": (60, 76, 4)}


def _gen_chordal(inst: str, bars: List[Dict[str, Any]], feel: Dict[str, Any], rng: random.Random) -> List[Dict[str, Any]]:
    low, high, max_notes = _COMP_RANGE[inst]
    events: List[Dict[str, Any]] = []
    target = (low + high) / 2.0
    for bar, chord in enumerate(bars):
        voicing = _closest_voicing(_chord_tones(chord), low, high, target, max_notes)
        target = sum(voicing) / float(len(voicing))
        template = _COMP_TEMPLATES[_pick(feel["comp"], rng)]
        if inst == "ukulele":
            template = [t for t in template if abs(t[0] % 1) < 1e-9 or t[0] == 1.5]
        for pos, dur, vel in template:
            if len(template) > 4 and rng.random() < 0.12:
                continue  # drop an occasional hit so each take breathes differently
            upstroke = abs((pos % 1.0) - 0.5) < 1e-9
            order = list(reversed(voicing)) if upstroke else list(voicing)
            for idx, midi in enumerate(order):
                ev = _event(bar, _swing_pos(pos, feel["swing"]) + idx * 0.012, dur, midi, vel - idx * 2, feel["vel_scale"], rng, 4)
                events.append(ev)
        if inst == "acoustic_piano":  # left hand: root + fifth underneath
            root = _lowest_at_or_above(chord["root_pc"], 38)
            for midi in (root, root + 7):
                events.append(_event(bar, 0.0, 3.0, midi, 70, feel["vel_scale"], rng, 4))
    events.sort(key=lambda e: (e["beat"], e["midi"]))
    return events


_SAX_MOTIFS = [
    [(0, 1.5), (1.5, .5), (2, 2)],
    [(.5, .5), (1, 1), (2.5, 1.5)],
    [(0, .75), (.75, .75), (1.5, .5), (2, 1), (3, 1)],
    [(1, 1), (2, .5), (2.5, .5), (3, 1)],
    [(0, 3.5)],
    [(0, 1), (1.5, .5), (2, .5), (2.5, 1.5)],
]


def _gen_sax(bars: List[Dict[str, Any]], key_pc: int, minor: bool, feel: Dict[str, Any], rng: random.Random) -> List[Dict[str, Any]]:
    scale = {(key_pc + i) % 12 for i in (MINOR_SCALE if minor else MAJOR_SCALE)}
    low, high = 58, 77
    prev = _lowest_at_or_above(bars[0]["root_pc"], 62)
    events: List[Dict[str, Any]] = []
    for bar, chord in enumerate(bars):
        last_bar = bar == len(bars) - 1
        if not last_bar and bar % 4 == 3 and rng.random() < 0.45:
            continue  # leave space at phrase ends
        tones = set(_chord_tones(chord))
        motif = [(0, 3.5)] if last_bar else rng.choice(_SAX_MOTIFS)
        for pos, dur in motif:
            strong = pos in (0, 2)
            allowed = tones if (strong or last_bar) else (tones | scale)
            cands = [m for m in range(low, high + 1) if m % 12 in allowed]
            if last_bar:
                cands = [m for m in cands if m % 12 == chord["root_pc"]]
            cands.sort(key=lambda m: (abs(m - prev), m))
            pool = [m for m in cands if m != prev] or cands
            midi = pool[min(len(pool) - 1, rng.randint(0, 2))] if not last_bar else cands[0]
            prev = midi
            events.append(_event(bar, _swing_pos(pos, feel["swing"]), dur * 0.92, midi, 88 if strong else 76, feel["vel_scale"], rng, 6))
    events.sort(key=lambda e: (e["beat"], e["midi"]))
    return events


def _gen_piccolo(bars: List[Dict[str, Any]], feel: Dict[str, Any], rng: random.Random) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    slots = [0.5, 1.0, 1.5, 2.5, 3.0, 3.5]
    for bar, chord in enumerate(bars):
        if bar % 2 == 1 and rng.random() < 0.4:
            continue
        tones = sorted(_lowest_at_or_above(pc, 79) for pc in _chord_tones(chord))
        count = rng.choice([2, 3])
        picks = sorted(rng.sample(slots, count))
        direction = rng.choice([1, -1])
        idx = 0 if direction == 1 else len(tones) - 1
        for pos in picks:
            midi = tones[idx % len(tones)] + (12 if idx >= len(tones) else 0)
            midi = min(midi, 96)
            events.append(_event(bar, _swing_pos(pos, feel["swing"]), 0.35, midi, 80, feel["vel_scale"], rng, 6))
            idx += direction
    events.sort(key=lambda e: (e["beat"], e["midi"]))
    return events


_CYM_PATTERNS = {
    "hat8": [(i * 0.5, 0.25, 42, 88 if i % 2 == 0 else 62) for i in range(8)],
    "ride_swing": [(0, 1, 51, 88), (1, 1, 51, 78), (1.5, 0.5, 51, 62), (2, 1, 51, 86), (3, 1, 51, 78), (3.5, 0.5, 51, 62)],
    "ride_quarters": [(0, 1, 51, 82), (1, 1, 51, 70), (2, 1, 51, 80), (3, 1, 51, 70)],
    "funk_cym": [(i * 0.25, 0.2, 42, 94 if i % 4 == 0 else (78 if i % 2 == 0 else 58)) for i in range(16)],
    "bossa_cym": [(0, 0.5, 42, 86), (0.75, 0.5, 42, 74), (1.5, 0.5, 42, 84), (2.25, 0.5, 42, 76), (3.0, 0.5, 42, 86), (3.75, 0.25, 42, 72)],
    "one_drop": [(1.0, 0.5, 42, 86), (2.0, 1.0, 51, 98), (3.0, 0.5, 42, 86)],
}


def _gen_cymbals(bars: List[Dict[str, Any]], feel: Dict[str, Any], rng: random.Random) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    base = _CYM_PATTERNS[feel["cym"]]
    for bar in range(len(bars)):
        pattern = base
        if feel["cym"] == "hat8" and rng.random() < 0.3:
            pattern = [p for p in base if p[0] != 1.5 or rng.random() < 0.5]
        for pos, dur, midi, vel in pattern:
            events.append(_event(bar, _swing_pos(pos, feel["swing"]), dur, midi, vel, feel["vel_scale"], rng))
        if bar % 4 == 0 and (bar == 0 or rng.random() < 0.7):
            events.append(_event(bar, 0.0, 2.0, 49, 100, feel["vel_scale"], rng, 4))
        elif feel["cym"] == "hat8" and bar % 2 == 1 and rng.random() < 0.35:
            events.append(_event(bar, 3.5, 0.5, 46, 84, feel["vel_scale"], rng, 4))
    events.sort(key=lambda e: (e["beat"], e["midi"]))
    return events


_KICK_PATTERNS = {
    "four": [(0, 98), (1, 82), (2, 94), (3, 82)],
    "sync": [(0, 100), (1.5, 80), (2.5, 90)],
    "half": [(0, 100), (2.75, 84)],
    "funk_kick": [(0, 102), (0.75, 84), (1.75, 88), (2.5, 94)],
    "bossa_kick": [(0, 92), (1.5, 84), (2.0, 90), (3.5, 82)],
    "one_drop_kick": [(2.0, 102)],
}


def _gen_kick(bars: List[Dict[str, Any]], feel: Dict[str, Any], rng: random.Random) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for bar in range(len(bars)):
        for pos, vel in _KICK_PATTERNS[_pick(feel["kick"], rng)]:
            events.append(_event(bar, _swing_pos(pos, feel["swing"]), 0.4, 36, vel, feel["vel_scale"], rng))
    events.sort(key=lambda e: (e["beat"], e["midi"]))
    return events


def _gen_floor_tom(bars: List[Dict[str, Any]], feel: Dict[str, Any], rng: random.Random) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for bar in range(len(bars)):
        events.append(_event(bar, 0.0, 0.8, 41, 96, feel["vel_scale"], rng))
        if rng.random() < 0.6:
            events.append(_event(bar, _swing_pos(2.5, feel["swing"]), 0.6, 41, 82, feel["vel_scale"], rng))
        if bar % 2 == 1:
            for pos, vel in ((3.0, 80), (3.5, 90)):
                events.append(_event(bar, _swing_pos(pos, feel["swing"]), 0.4, 41, vel, feel["vel_scale"], rng))
    events.sort(key=lambda e: (e["beat"], e["midi"]))
    return events


_BONGO_PATTERN = [(0, 61, 74), (1, 60, 88), (1.5, 60, 76), (2, 61, 72), (2.5, 60, 84), (3.5, 61, 70)]


def _gen_bongos(bars: List[Dict[str, Any]], feel: Dict[str, Any], rng: random.Random) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for bar in range(len(bars)):
        for pos, midi, vel in _BONGO_PATTERN:
            if rng.random() < 0.1:
                continue
            events.append(_event(bar, _swing_pos(pos, feel["swing"]), 0.3, midi, vel, feel["vel_scale"], rng))
    events.sort(key=lambda e: (e["beat"], e["midi"]))
    return events


def _gen_triangle(bars: List[Dict[str, Any]], feel: Dict[str, Any], rng: random.Random) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for bar in range(len(bars)):
        positions = [1.5, 3.5] if rng.random() < 0.6 else [0.5, 2.5]
        for pos in positions:
            events.append(_event(bar, _swing_pos(pos, feel["swing"]), 1.5, 81, 72, feel["vel_scale"], rng, 6))
        if bar % 4 == 3:
            events.append(_event(bar, 3.0, 0.5, 80, 60, feel["vel_scale"], rng, 4))
    events.sort(key=lambda e: (e["beat"], e["midi"]))
    return events


def _gen_drum_kit(bars: List[Dict[str, Any]], feel: Dict[str, Any], rng: random.Random) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    swing = feel.get("swing", 0.0)
    vel_scale = feel.get("vel_scale", 1.0)
    tags = feel.get("tags", [])
    is_halftime = "halftime-shuffle" in tags or "half-time" in tags or feel.get("groove") == "half_time"

    for bar in range(len(bars)):
        if is_halftime:
            # Kick on 0, Snare on 2 (beat 3 of bar)
            events.append(_event(bar, 0.0, 0.5, 36, 108, vel_scale, rng, 2))
            events.append(_event(bar, 2.0, 0.5, 38, 104, vel_scale, rng, 2))
        else:
            # Kick on 0, 2; Snare on 1, 3
            events.append(_event(bar, 0.0, 0.5, 36, 108, vel_scale, rng, 2))
            events.append(_event(bar, 1.0, 0.5, 38, 102, vel_scale, rng, 2))
            events.append(_event(bar, 2.0, 0.5, 36, 96, vel_scale, rng, 2))
            events.append(_event(bar, 3.0, 0.5, 38, 102, vel_scale, rng, 2))

        # Hi-Hats: 8ths across bar (swung if swing > 0)
        for b in range(4):
            events.append(_event(bar, float(b), 0.3, 42, 84, vel_scale, rng, 2))
            swung_upbeat = _swing_pos(b + 0.5, swing) if swing > 0 else (b + 0.5)
            events.append(_event(bar, swung_upbeat, 0.3, 42, 68, vel_scale, rng, 2))

        # Accent crash on bar 0 downbeat
        if bar == 0:
            events.append(_event(bar, 0.0, 2.0, 49, 96, vel_scale, rng, 1))

    events.sort(key=lambda e: (e["beat"], e["midi"]))
    return events


def _generate_lane(inst: str, bars: List[Dict[str, Any]], key_pc: int, minor: bool, feel: Dict[str, Any], rng: random.Random) -> List[Dict[str, Any]]:
    if inst in ("bass_guitar", "contrabass"):
        return _gen_bass(inst, bars, feel, rng)
    if inst in ("rhythm_guitar", "acoustic_piano", "ukulele"):
        return _gen_chordal(inst, bars, feel, rng)
    if inst == "tenor_sax":
        return _gen_sax(bars, key_pc, minor, feel, rng)
    if inst == "piccolo":
        return _gen_piccolo(bars, feel, rng)
    if inst == "drum_kit":
        return _gen_drum_kit(bars, feel, rng)
    if inst == "cymbals":
        return _gen_cymbals(bars, feel, rng)
    if inst == "bass_drums":
        return _gen_kick(bars, feel, rng)
    if inst == "floor_tom":
        return _gen_floor_tom(bars, feel, rng)
    if inst == "bongos":
        return _gen_bongos(bars, feel, rng)
    if inst == "triangle":
        return _gen_triangle(bars, feel, rng)
    raise ValueError("Unknown instrument: `%s`" % inst)


# --------------------------------------------------------------------------
# Locking, hashing, validation
# --------------------------------------------------------------------------
def is_locked(tier: str, instrument: str, locked_parts: Optional[List[str]]) -> bool:
    for part in locked_parts or []:
        token = str(part).strip().lower()
        if token in (tier, instrument) or LANE_ALIAS.get(token) == tier:
            return True
    return False


def events_hash(events: List[Dict[str, Any]]) -> str:
    """Canonical SHA-256 of a lane. Numbers are formatted, so 4 and 4.0 hash alike."""
    canon = ";".join("%.4f:%.4f:%d:%d" % (e["beat"], e["dur"], e["midi"], e["vel"]) for e in events)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def sanitize_events(events: Any, loop_bars: int) -> Optional[List[Dict[str, Any]]]:
    """Validate events coming back from the client. Returns None if anything is off."""
    if not isinstance(events, list) or len(events) > MAX_EVENTS_PER_LANE:
        return None
    clean: List[Dict[str, Any]] = []
    limit = loop_bars * BEATS_PER_BAR
    for ev in events:
        if not isinstance(ev, dict):
            return None
        try:
            beat, dur, midi, vel = float(ev["beat"]), float(ev["dur"]), int(ev["midi"]), int(ev["vel"])
        except (KeyError, TypeError, ValueError):
            return None
        if not (0 <= beat < limit and 0 < dur <= 16 and 0 <= midi <= 127 and 1 <= vel <= 127):
            return None
        clean.append({"beat": round(beat, 4), "dur": round(dur, 4), "midi": midi, "vel": vel})
    return clean


def compose(
    chords: List[str],
    key: str,
    instruments: List[str],
    prompt: str = "",
    seed: int = 1,
    locked_parts: Optional[List[str]] = None,
    previous_score: Optional[Dict[str, Any]] = None,
    groove: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the symbolic score. Locked lanes are copied verbatim from previous_score."""
    if not chords:
        raise ValueError("Enter at least one chord.")
    parsed = [parse_chord(token, key) for token in chords]
    key_pc, minor = parse_key(key)
    loop_bars = 16 if len(parsed) > 8 else 8
    bars = _bars_to_chords(parsed, loop_bars)
    feel = parse_feel(prompt)
    if groove == "swing":
        feel["swing"] = max(feel.get("swing", 0), 0.667)
    elif groove == "half_time":
        feel["kick"] = "half"
    symbols = [c["symbol"] for c in parsed]

    previous_lanes: Dict[Tuple[str, str], Dict[str, Any]] = {}
    previous_chords: Optional[List[str]] = None
    if isinstance(previous_score, dict) and isinstance(previous_score.get("lanes"), list):
        previous_chords = [b.get("chord") for b in previous_score.get("bars", []) if isinstance(b, dict)]
        if previous_score.get("loop_bars") == loop_bars:
            for lane in previous_score["lanes"]:
                if isinstance(lane, dict):
                    previous_lanes[(str(lane.get("tier")), str(lane.get("instrument")))] = lane

    lanes: List[Dict[str, Any]] = []
    warnings: List[str] = []
    for inst in instruments:
        tier = INSTRUMENT_TIER.get(inst)
        if tier is None:
            raise ValueError("Unknown instrument: `%s`" % inst)
        locked = is_locked(tier, inst, locked_parts)
        events: Optional[List[Dict[str, Any]]] = None
        source = "generated"
        if locked:
            prior = previous_lanes.get((tier, inst))
            events = sanitize_events(prior.get("events"), loop_bars) if prior else None
            if events is not None:
                source = "locked_copy"
                if previous_chords and previous_chords != [b["chord"] for b in _bar_summary(bars)]:
                    warnings.append("Locked %s lane kept as-is; the chord progression changed." % inst)
            elif prior:
                warnings.append("Previous %s lane was invalid; regenerated it." % inst)
        if events is None:
            rng = random.Random("%s:%s:%s" % (seed, tier, inst))
            events = _generate_lane(inst, bars, key_pc, minor, feel, rng)
            if locked:
                source = "locked_anchor"  # cold start: generated now, frozen from here on
        lanes.append({
            "tier": tier, "instrument": inst, "locked": locked, "source": source,
            "hash": events_hash(events), "events": events,
        })

    return {
        "version": 1,
        "key": key,
        "beats_per_bar": BEATS_PER_BAR,
        "loop_bars": loop_bars,
        "seed": seed,
        "feel": {"tags": feel["tags"], "swing": feel["swing"]},
        "bars": _bar_summary(bars),
        "lanes": lanes,
        "warnings": warnings,
    }


def _bar_summary(bars: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{"bar": i + 1, "chord": c["symbol"]} for i, c in enumerate(bars)]


_CHORD_TOKEN_REGEX = re.compile(
    r"^(?:"
    r"[A-G][#b]?(?:maj|min|m|dim|aug|sus|add)?\d*(?:/[A-G][#b]?)?"
    r"|"
    r"[b#]?(?:[1-7]|vii|vi|iv|v|iii|ii|i)(?:maj|min|m|dim|aug|sus|add)?\d*(?:/[b#]?(?:[1-7]|vii|vi|iv|v|iii|ii|i))?"
    r")$",
    re.IGNORECASE,
)


def extract_musical_intent_from_prompt(
    prompt: Optional[str],
    current_key: Optional[str] = None,
    current_bpm: Optional[int] = None,
    current_chords: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Day 4 Prompt Co-Pilot:
    Extracts key, BPM, chord progression, and feel directly from natural language prompts.
    """
    text = (prompt or "").strip()
    feel = parse_feel(text)
    inferred_key = current_key
    inferred_bpm = current_bpm
    inferred_chords = None

    if text:
        # 1. Key extraction (e.g. "in G Major", "in Dm", "key: C", "key of Am")
        key_match = re.search(
            r"(?:in|key(?:\s+of)?[:\s]+)\s*([A-G][#b]?(?:maj|min|minor|major|m)?)\b",
            text,
            re.IGNORECASE,
        )
        if key_match:
            raw_k = key_match.group(1).strip()
            if re.search(r"minor|min\b", raw_k, re.IGNORECASE):
                root_m = re.match(r"^[A-G][#b]?", raw_k, re.IGNORECASE)
                if root_m:
                    root = root_m.group(0)
                    inferred_key = f"{root.upper()}m" if len(root) == 1 else f"{root[0].upper()}{root[1:]}m"
            elif re.search(r"major|maj\b", raw_k, re.IGNORECASE):
                root_m = re.match(r"^[A-G][#b]?", raw_k, re.IGNORECASE)
                if root_m:
                    root = root_m.group(0)
                    inferred_key = root.upper() if len(root) == 1 else f"{root[0].upper()}{root[1:]}"
            else:
                inferred_key = raw_k[0].upper() + raw_k[1:]

        # 2. BPM extraction (e.g. "110 BPM", "at 92 bpm", "tempo: 120")
        bpm_match = re.search(
            r"(\d{2,3})\s*(?:bpm|tempo)\b|\b(?:bpm|tempo)[:\s]+(\d{2,3})\b",
            text,
            re.IGNORECASE,
        )
        if bpm_match:
            bpm_val = int(bpm_match.group(1) or bpm_match.group(2))
            if 40 <= bpm_val <= 240:
                inferred_bpm = max(60, min(200, bpm_val))

        # 3. Chord progression extraction
        prog_match = re.search(
            r"(?:like|progression[:\s]+|chords?[:\s]+)([\w#b\s,\-–—/|]+?)(?=(?:\.|\bin\b|\bat\b|$))",
            text,
            re.IGNORECASE,
        )
        candidate_segment = prog_match.group(1) if prog_match else text
        tokens = [t.strip() for t in re.split(r"[\s,|\-–—]+", candidate_segment) if t.strip()]

        valid_chords: List[str] = []
        for t in tokens:
            if _CHORD_TOKEN_REGEX.match(t):
                if t.upper() in {"A", "I"} and len(tokens) < 3 and not prog_match:
                    continue
                valid_chords.append(t)
            elif valid_chords and len(valid_chords) >= 2:
                break

        if len(valid_chords) >= 2:
            inferred_chords = valid_chords
            if not inferred_key:
                last_chord = valid_chords[-1]
                match_last = _CHORD_RE.match(last_chord)
                if match_last and match_last.group(1):
                    inferred_key = match_last.group(1)

    return {
        "key": inferred_key or current_key or "Am",
        "bpm": inferred_bpm or current_bpm or 110,
        "chords": inferred_chords or (
            [t.strip() for t in re.split(r"[\s,|\-–—]+", current_chords) if t.strip()]
            if current_chords else ["Am", "F", "C", "G"]
        ),
        "feel": feel,
    }
