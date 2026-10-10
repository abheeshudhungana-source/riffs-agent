import os
import re
import json
import hashlib
import base64
from typing import List, Dict, Any, Optional
# Load secrets from .env if dotenv is installed
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Diatonic scale definitions and chord-to-tab mappings
CHROMATIC_SCALE = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT_TO_SHARP = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}


def _part_score_payload(instrument: str, score: Any) -> Dict[str, Any]:
    """Serialize a deterministic symbolic lane and its MIDI bytes."""
    from riffs_api.exports import midi_bytes
    from riffs_api.score import ScoreBar, ScoreDraft, ScoreNote

    low_end = {"bass_guitar", "contrabass", "bass_drums", "floor_tom"}
    high_end = {"cymbals", "triangle", "ukulele", "piccolo"}
    octave_shift = -12 if instrument in low_end else 12 if instrument in high_end else 0
    bars = tuple(
        ScoreBar(
            bar=bar.bar,
            chord_symbol=bar.chord_symbol,
            nashville=bar.nashville,
            notes=tuple(
                ScoreNote(
                    pitch_midi=note.pitch_midi + octave_shift,
                    onset_beats=note.onset_beats,
                    duration_beats=note.duration_beats,
                    velocity=note.velocity,
                )
                for note in bar.notes
            ),
        )
        for bar in score.bars
    )

    lane_score = ScoreDraft(
        key=score.key,
        tempo_bpm=score.tempo_bpm,
        time_signature=score.time_signature,
        beats_per_bar=score.beats_per_bar,
        chord_chart=score.chord_chart,
        nashville_chart=score.nashville_chart,
        bars=bars,
    )
    midi = midi_bytes(lane_score)
    serialized_bars = [
        {
            "bar": bar.bar,
            "chord_symbol": bar.chord_symbol,
            "notes": [
                {
                    "pitch_midi": note.pitch_midi,
                    "onset_beats": note.onset_beats,
                    "duration_beats": note.duration_beats,
                    "velocity": note.velocity,
                }
                for note in bar.notes
            ],
        }
        for bar in lane_score.bars
    ]
    return {
        "instrument": instrument,
        "tempo_bpm": lane_score.tempo_bpm,
        "chord_chart": lane_score.chord_chart,
        "nashville_chart": lane_score.nashville_chart,
        "bars": serialized_bars,
        "note_vector_sha256": hashlib.sha256(
            json.dumps(serialized_bars, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "midi_base64": base64.b64encode(midi).decode("ascii"),
        "midi_sha256": hashlib.sha256(midi).hexdigest(),
    }


def _reuse_locked_part(instrument: str, previous: Dict[str, Any], score: Any) -> Dict[str, Any]:
    """Keep a lane's prior note vectors while writing MIDI at the current tempo."""
    from riffs_api.exports import midi_bytes
    from riffs_api.score import ScoreBar, ScoreDraft, ScoreNote

    bars = tuple(
        ScoreBar(
            bar=bar["bar"],
            chord_symbol=bar["chord_symbol"],
            nashville=None,
            notes=tuple(ScoreNote(**note) for note in bar["notes"]),
        )
        for bar in previous["bars"]
    )
    lane_score = ScoreDraft(
        key=score.key,
        tempo_bpm=score.tempo_bpm,
        time_signature=score.time_signature,
        beats_per_bar=score.beats_per_bar,
        chord_chart=previous.get("chord_chart", score.chord_chart),
        nashville_chart=previous.get("nashville_chart", score.nashville_chart),
        bars=bars,
    )
    midi = midi_bytes(lane_score)
    payload = dict(previous)
    payload.update({
        "instrument": instrument,
        "tempo_bpm": lane_score.tempo_bpm,
        "midi_base64": base64.b64encode(midi).decode("ascii"),
        "midi_sha256": hashlib.sha256(midi).hexdigest(),
    })
    return payload


_LOCK_ALIASES = {
    "bass": {"bass_guitar", "contrabass", "bass_drums"},
    "rhythm": {"rhythm_guitar", "acoustic_piano", "ukulele"},
    "lead": {"tenor_sax", "piccolo"},
    "drums": {"bass_drums", "floor_tom", "bongos", "cymbals", "triangle"},
}


def _locked_part(instrument: str, locked_parts: List[str]) -> bool:
    lane = instrument.lower()
    return any(
        lock.lower() == lane
        or lock.lower() in lane
        or lane in _LOCK_ALIASES.get(lock.lower(), set())
        for lock in locked_parts
    )

MAJOR_INTERVALS = [0, 2, 4, 5, 7, 9, 11]
MINOR_INTERVALS = [0, 2, 3, 5, 7, 8, 10]

COMMON_GUITAR_CHORDS: Dict[str, List[str]] = {
    "C":    ["x", "3", "2", "0", "1", "0"],
    "Cmaj7":["x", "3", "2", "0", "0", "0"],
    "Cm":   ["x", "3", "5", "5", "4", "3"],
    "D":    ["x", "x", "0", "2", "3", "2"],
    "Dm":   ["x", "x", "0", "2", "3", "1"],
    "Dm7":  ["x", "x", "0", "2", "1", "1"],
    "E":    ["0", "2", "2", "1", "0", "0"],
    "Em":   ["0", "2", "2", "0", "0", "0"],
    "Em7":  ["0", "2", "0", "0", "0", "0"],
    "F":    ["1", "3", "3", "2", "1", "1"],
    "Fmaj7":["x", "x", "3", "2", "1", "0"],
    "Fm":   ["1", "3", "3", "1", "1", "1"],
    "G":    ["3", "2", "0", "0", "0", "3"],
    "G7":   ["3", "2", "0", "0", "0", "1"],
    "Gm":   ["3", "5", "5", "3", "3", "3"],
    "A":    ["x", "0", "2", "2", "2", "0"],
    "Am":   ["x", "0", "2", "2", "1", "0"],
    "Am7":  ["x", "0", "2", "0", "1", "0"],
    "B":    ["x", "2", "4", "4", "4", "2"],
    "Bm":   ["x", "2", "4", "4", "3", "2"],
    "Bm7":  ["x", "2", "4", "2", "3", "2"],
}

def normalize_root(pitch: str) -> str:
    pitch = pitch.strip()
    return FLAT_TO_SHARP.get(pitch, pitch)

def parse_chord_tokens(raw_chords: str) -> List[str]:
    clean = (raw_chords or "").strip()
    if not clean:
        return ["Am", "F", "C", "G"]
    tokens = re.split(r"[\s,|\-–—]+", clean)
    return [t.strip() for t in tokens if t.strip()]

def calculate_nashville_numbers(chords: List[str], key: str = "Am") -> List[str]:
    """Map chord names to Nashville Number representations."""
    is_minor = key.endswith("m")
    key_root = key[:-1] if is_minor else key
    norm_key = normalize_root(key_root)

    try:
        key_idx = CHROMATIC_SCALE.index(norm_key)
    except ValueError:
        key_idx = CHROMATIC_SCALE.index("A" if is_minor else "C")

    nashville_chart: List[str] = []

    for token in chords:
        # Check if already Nashville format (e.g. 1, 1m, 4, 5, b6)
        if re.match(r"^[b#]?[1-7]", token):
            nashville_chart.append(token)
            continue

        match = re.match(r"^([A-G][#b]?)(.*)$", token)
        if not match:
            nashville_chart.append(token)
            continue

        root, quality = match.groups()
        norm_root = normalize_root(root)
        try:
            root_idx = CHROMATIC_SCALE.index(norm_root)
        except ValueError:
            nashville_chart.append(token)
            continue

        interval = (root_idx - key_idx) % 12

        if is_minor:
            # Minor key scale degrees (Natural Minor: 0, 2, 3, 5, 7, 8, 10)
            deg_map = {0: "1m", 2: "2", 3: "b3", 5: "4", 7: "5", 8: "b6", 10: "b7"}
            degree = deg_map.get(interval, str(interval))
        else:
            # Major key scale degrees (Major: 0, 2, 4, 5, 7, 9, 11)
            deg_map = {0: "1", 2: "2", 4: "3", 5: "4", 7: "5", 9: "6", 11: "7"}
            degree = deg_map.get(interval, str(interval))
            if "m" in quality and not quality.startswith("maj"):
                degree += "m"

        nashville_chart.append(degree)

    return nashville_chart

def generate_tab_score(chords: List[str]) -> str:
    """Generate clean 6-string guitar tab representation for the progression."""
    string_names = ["e", "B", "G", "D", "A", "E"]
    lines = {s: f"{s}|" for s in string_names}

    for chord in chords:
        base_chord = chord.split("/")[0]
        frets = COMMON_GUITAR_CHORDS.get(base_chord, COMMON_GUITAR_CHORDS.get(base_chord + "m", ["x", "x", "x", "x", "x", "x"]))
        # frets order is E, A, D, G, B, e
        rev_frets = list(reversed(frets)) # e, B, G, D, A, E
        for idx, s in enumerate(string_names):
            lines[s] += f"---{rev_frets[idx]}---|"

    return "\n".join([lines[s] for s in string_names])

class RiffsAgent:
    """
    Autonomous AI Practice & Sketching Partner for Musicians.
    Implements Day 1 Symbolic Score Generation and Part-Locking.
    """
    def __init__(self, model_id: str = "anthropic/claude-sonnet-5-5"):
        self.model_id = model_id
        self.api_key = ANTHROPIC_API_KEY
        self.max_tokens = 4096
        self.take_history: List[Dict[str, Any]] = []
        self._next_take_id = 1

    def generate(
        self,
        prompt: str,
        key: str = "Am",
        bpm: int = 110,
        chords: str = "Am - F - C - G",
        instruments: Optional[List[str]] = None,
        locked_parts: Optional[List[str]] = None,
        base_take_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Executes Day 1 symbolic blueprint generation with part-locking.
        """
        instruments = instruments or ["bass_guitar", "rhythm_guitar", "cymbals"]
        locked_parts = locked_parts or []
        bpm = max(60, min(200, int(bpm or 110)))
        key = key or "Am"

        parsed_chords = parse_chord_tokens(chords)
        nashville_chart = calculate_nashville_numbers(parsed_chords, key)
        tab_score = generate_tab_score(parsed_chords)

        # Keep a deterministic symbolic representation beside the UI chart data.
        # A locked lane reuses its exact note vectors and refreshes global tempo metadata.
        from riffs_api.score import draft_score

        symbolic_score = draft_score(chords, key, bpm)
        base_take = next(
            (take for take in self.take_history if take["take_id"] == base_take_id),
            None,
        ) if base_take_id is not None else (self.take_history[-1] if self.take_history else None)
        previous_data = base_take["data"] if base_take else {}
        previous_parts = previous_data.get("part_scores", {})
        part_scores: Dict[str, Dict[str, Any]] = {}
        for inst in instruments:
            lock_requested = _locked_part(inst, locked_parts)
            prior_lane = previous_parts.get(inst)
            if lock_requested and prior_lane is not None:
                lane_payload = _reuse_locked_part(inst, prior_lane, symbolic_score)
            else:
                lane_payload = _part_score_payload(inst, symbolic_score)
            lane_payload["locked"] = bool(lock_requested)
            part_scores[inst] = lane_payload

        # Build stems
        stems = []
        for inst in instruments:
            safe_inst = re.sub(r"[^a-zA-Z0-9_]", "_", inst)
            is_locked = _locked_part(inst, locked_parts)
            stems.append({
                "lane": inst,
                "filename": f"riff_{key}_{bpm}bpm_{safe_inst}.mid",
                "locked": is_locked,
                "available": True,
                "format": "midi",
                "midi_sha256": part_scores[inst]["midi_sha256"],
                "note_vector_sha256": part_scores[inst]["note_vector_sha256"],
            })

        # Do not claim royalty-free rights until a verified sample source is selected.
        license_cert = {
            "license_id": None,
            "status": "not_issued",
            "reason": "No verified licensed audio sample source is configured.",
        }

        # Try Anthropic Claude if API key is present
        claude_enhancement = None
        if self.api_key:
            try:
                import litellm
                system_prompt = (
                    "You are RIFFs, an autonomous music theory and acoustic sketching co-producer.\n"
                    "Generate a concise JSON response refining the groove, rhythmic feel, and musician directions.\n"
                    "Respond with pure valid JSON matching:\n"
                    '{"style_notes": "...", "groove_feel": "...", "dynamic_variation": "..."}'
                )
                user_msg = f"Key: {key}, BPM: {bpm}, Chords: {parsed_chords}, Instruments: {instruments}, Prompt: {prompt}"
                resp = litellm.completion(
                    model=self.model_id,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_msg}
                    ],
                    api_key=self.api_key,
                    max_tokens=500
                )
                content = resp.choices[0].message.content
                # Strip markdown code blocks if present
                content_clean = re.sub(r"^```json\s*|\s*```$", "", content.strip())
                claude_enhancement = json.loads(content_clean)
            except Exception as e:
                # Graceful fallback: continue with deterministic symbolic engine
                pass

        result_data = {
            "key": key,
            "bpm": bpm,
            "chords": parsed_chords,
            "nashville_chart": nashville_chart,
            "tab_score": tab_score,
            "stems": stems,
            "take_id": self._next_take_id,
            "part_scores": part_scores,
            "license_certificate": license_cert
        }

        if claude_enhancement:
            result_data["ai_enrichment"] = claude_enhancement

        # Store in take history for part-locking non-destructive stack
        take_id = self._next_take_id
        self._next_take_id += 1
        self.take_history.append({"take_id": take_id, "data": result_data})
        del self.take_history[:-5]

        return result_data
