"""Symbolic score export formats used by the RIFFs render tool."""

from __future__ import annotations

import json
import struct
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from riffs_api.score import ScoreDraft


@dataclass(frozen=True)
class ExportFile:
    filename: str
    media_type: str
    content: bytes


_PITCH_NAMES = (
    ("C", 0), ("C", 1), ("D", 0), ("D", 1), ("E", 0), ("F", 0),
    ("F", 1), ("G", 0), ("G", 1), ("A", 0), ("A", 1), ("B", 0),
)


def _midi_variable_length(value: int) -> bytes:
    buffer = value & 0x7F
    result = bytearray()
    while (value := value >> 7):
        buffer <<= 8
        buffer |= ((value & 0x7F) | 0x80)
    while True:
        result.append(buffer & 0xFF)
        if buffer & 0x80:
            buffer >>= 8
        else:
            break
    return bytes(result)


def midi_bytes(score: ScoreDraft) -> bytes:
    ticks_per_beat = 480
    microseconds_per_beat = round(60_000_000 / score.tempo_bpm)
    events: list[tuple[int, int, bytes]] = [
        (0, 0, b"\xff\x03\x05RIFFs"),
        (0, 1, b"\xff\x51\x03" + microseconds_per_beat.to_bytes(3, "big")),
        (0, 2, b"\xff\x58\x04\x04\x02\x18\x08"),
    ]

    for bar_index, bar in enumerate(score.bars):
        bar_start = bar_index * score.beats_per_bar * ticks_per_beat
        for note in bar.notes:
            start = bar_start + note.onset_beats * ticks_per_beat
            end = start + note.duration_beats * ticks_per_beat
            events.append((start, 4, bytes((0x90, note.pitch_midi, note.velocity))))
            events.append((end, 3, bytes((0x80, note.pitch_midi, 0))))

    last_tick = max((event[0] for event in events), default=0)
    events.append((last_tick, 5, b"\xff\x2f\x00"))
    events.sort(key=lambda event: (event[0], event[1]))

    track = bytearray()
    previous_tick = 0
    for tick, _, payload in events:
        track.extend(_midi_variable_length(tick - previous_tick))
        track.extend(payload)
        previous_tick = tick

    header = b"MThd" + struct.pack(">IHHH", 6, 0, 1, ticks_per_beat)
    return header + b"MTrk" + struct.pack(">I", len(track)) + bytes(track)


def _pitch_xml(pitch_midi: int) -> tuple[str, int, int]:
    pitch_class = pitch_midi % 12
    step, alter = _PITCH_NAMES[pitch_class]
    octave = pitch_midi // 12 - 1
    return step, alter, octave


def musicxml_bytes(score: ScoreDraft) -> bytes:
    root = ET.Element("score-partwise", version="3.1")
    if score.key:
        identification = ET.SubElement(root, "identification")
        miscellaneous = ET.SubElement(identification, "miscellaneous")
        ET.SubElement(miscellaneous, "miscellaneous-field", name="key").text = score.key
    part_list = ET.SubElement(root, "part-list")
    score_part = ET.SubElement(part_list, "score-part", id="P1")
    ET.SubElement(score_part, "part-name").text = "RIFFs Chords"
    part = ET.SubElement(root, "part", id="P1")

    for bar in score.bars:
        measure = ET.SubElement(part, "measure", number=str(bar.bar))
        if bar.bar == 1:
            attributes = ET.SubElement(measure, "attributes")
            ET.SubElement(attributes, "divisions").text = "1"
            time = ET.SubElement(attributes, "time")
            ET.SubElement(time, "beats").text = "4"
            ET.SubElement(time, "beat-type").text = "4"
        if bar.bar == 1:
            direction = ET.SubElement(measure, "direction", placement="above")
            direction_type = ET.SubElement(direction, "direction-type")
            metronome = ET.SubElement(direction_type, "metronome")
            ET.SubElement(metronome, "beat-unit").text = "quarter"
            ET.SubElement(metronome, "per-minute").text = str(score.tempo_bpm)
            sound = ET.SubElement(direction, "sound", tempo=str(score.tempo_bpm))

        for note_index, score_note in enumerate(bar.notes):
            note = ET.SubElement(measure, "note")
            if note_index:
                ET.SubElement(note, "chord")
            step, alter, octave = _pitch_xml(score_note.pitch_midi)
            pitch = ET.SubElement(note, "pitch")
            ET.SubElement(pitch, "step").text = step
            if alter:
                ET.SubElement(pitch, "alter").text = str(alter)
            ET.SubElement(pitch, "octave").text = str(octave)
            ET.SubElement(note, "duration").text = str(score_note.duration_beats)
            ET.SubElement(note, "voice").text = "1"
            ET.SubElement(note, "type").text = "whole"

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def chord_chart_json_bytes(score: ScoreDraft) -> bytes:
    payload = {
        "key": score.key,
        "tempo_bpm": score.tempo_bpm,
        "time_signature": score.time_signature,
        "chord_chart": score.chord_chart,
        "nashville_chart": score.nashville_chart,
        "bars": [
            {
                "bar": bar.bar,
                "chord_symbol": bar.chord_symbol,
                "nashville": bar.nashville,
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
            for bar in score.bars
        ],
    }
    return json.dumps(payload, indent=2).encode("utf-8")


def key_filename_slug(key: str | None) -> str:
    if not key:
        return "Cmaj"
    parts = key.strip().split()
    root = parts[0].replace("#", "s")
    mode = parts[1].lower() if len(parts) > 1 else "major"
    return root + ("min" if mode in {"minor", "min", "m"} else "maj")


def export_symbolic_score(score: ScoreDraft) -> tuple[ExportFile, ...]:
    key_slug = key_filename_slug(score.key)
    tempo_slug = f"{score.tempo_bpm}bpm"
    stem = f"riff_{key_slug}_{tempo_slug}"
    return (
        ExportFile(f"{stem}.mid", "audio/midi", midi_bytes(score)),
        ExportFile(f"{stem}.musicxml", "application/vnd.recordare.musicxml+xml", musicxml_bytes(score)),
        ExportFile(f"{stem}_chord_chart.json", "application/json", chord_chart_json_bytes(score)),
    )
