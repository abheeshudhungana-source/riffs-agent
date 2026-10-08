"""Deterministic tests for the symbolic render pipeline."""

from __future__ import annotations

import json
import sys
import unittest
import xml.etree.ElementTree as ET
import zipfile
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from riffs_api.progression import parse_progression
from riffs_api.render import render_symbolic_package
from riffs_api.score import draft_score
from riffs_api.routes import ParseProgressionRequest, render_riff_to_audio_endpoint


def _read_variable_length(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    while True:
        byte = data[offset]
        offset += 1
        value = (value << 7) | (byte & 0x7F)
        if byte < 0x80:
            return value, offset


def _midi_note_ons(data: bytes) -> list[tuple[int, int, int]]:
    track_offset = 14
    if data[track_offset:track_offset + 4] != b"MTrk":
        raise AssertionError("MIDI track chunk is missing")
    track_length = int.from_bytes(data[track_offset + 4:track_offset + 8], "big")
    track = data[track_offset + 8:track_offset + 8 + track_length]
    offset = 0
    tick = 0
    note_ons: list[tuple[int, int, int]] = []
    while offset < len(track):
        delta, offset = _read_variable_length(track, offset)
        tick += delta
        status = track[offset]
        offset += 1
        if status == 0xFF:
            offset += 1  # meta event type
            length, offset = _read_variable_length(track, offset)
            offset += length
            continue
        first, second = track[offset], track[offset + 1]
        offset += 2
        if status == 0x90 and second:
            note_ons.append((tick, first, second))
    return note_ons


class RenderTests(unittest.TestCase):
    def test_nashville_degrees_resolve_from_g_major_scale(self) -> None:
        parsed = parse_progression("vi - IV - I - V", "G major")
        tonic_pitch_class = 7  # G
        major_scale_intervals = (0, 2, 4, 5, 7, 9, 11)
        degree_by_token = {"vi": 6, "IV": 4, "I": 1, "V": 5}
        quality_by_degree = ("major", "minor", "minor", "major", "major", "minor", "diminished")

        for chord in parsed.chords:
            degree = degree_by_token[chord.source]
            expected_pitch_class = (tonic_pitch_class + major_scale_intervals[degree - 1]) % 12
            self.assertEqual(chord.scale_degree, degree)
            self.assertEqual(chord.pitch_class, expected_pitch_class)
            self.assertEqual(chord.quality, quality_by_degree[degree - 1])

    def test_same_sixth_degree_follows_a_different_key(self) -> None:
        parsed = parse_progression("vi", "C major")
        chord = parsed.chords[0]
        self.assertEqual(chord.pitch_class, 9)  # A
        self.assertEqual(chord.quality, "minor")
        self.assertEqual(chord.symbol, "Am")

    def test_render_package_contains_exact_symbolic_exports(self) -> None:
        package_bytes = render_symbolic_package("vi - IV - I - V", "G major", 110)
        with zipfile.ZipFile(BytesIO(package_bytes)) as package:
            self.assertEqual(
                set(package.namelist()),
                {
                    "manifest.json",
                    "riff_Gmaj_110bpm.mid",
                    "riff_Gmaj_110bpm.musicxml",
                    "riff_Gmaj_110bpm_chord_chart.json",
                },
            )
            manifest = json.loads(package.read("manifest.json"))
            chart = json.loads(package.read("riff_Gmaj_110bpm_chord_chart.json"))
            midi = package.read("riff_Gmaj_110bpm.mid")
            musicxml = ET.fromstring(package.read("riff_Gmaj_110bpm.musicxml"))

        self.assertEqual(manifest["chord_chart"], "| Em | C | G | D |")
        self.assertEqual(manifest["nashville_chart"], "| 6m | 4 | 1 | 5 |")
        self.assertFalse(manifest["audio_rendered"])
        self.assertIsNone(manifest["license_certificate"])
        self.assertEqual(chart["tempo_bpm"], 110)
        self.assertEqual([bar["chord_symbol"] for bar in chart["bars"]], ["Em", "C", "G", "D"])

        self.assertEqual(midi[:4], b"MThd")
        self.assertEqual(
            _midi_note_ons(midi),
            [
                (0, 64, 80), (0, 67, 80), (0, 71, 80),
                (1920, 60, 80), (1920, 64, 80), (1920, 67, 80),
                (3840, 67, 80), (3840, 71, 80), (3840, 74, 80),
                (5760, 62, 80), (5760, 66, 80), (5760, 69, 80),
            ],
        )
        pitches = [
            (pitch.findtext("step"), pitch.findtext("alter"), pitch.findtext("octave"))
            for pitch in musicxml.findall(".//pitch")
        ]
        self.assertEqual(
            pitches,
            [
                ("E", None, "4"), ("G", None, "4"), ("B", None, "4"),
                ("C", None, "4"), ("E", None, "4"), ("G", None, "4"),
                ("G", None, "4"), ("B", None, "4"), ("D", None, "5"),
                ("D", None, "4"), ("F", "1", "4"), ("A", None, "4"),
            ],
        )

    def test_render_endpoint_returns_downloadable_zip(self) -> None:
        response = render_riff_to_audio_endpoint(ParseProgressionRequest(
            progression="vi - IV - I - V",
            key="G major",
            tempo_bpm=110,
        ))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.media_type, "application/zip")
        self.assertIn("riff_Gmaj_110bpm_symbolic.zip", response.headers["content-disposition"])
        with zipfile.ZipFile(BytesIO(response.body)) as package:
            manifest = json.loads(package.read("manifest.json"))
        self.assertEqual(manifest["status"], "symbolic_exports_ready")


if __name__ == "__main__":
    unittest.main()
