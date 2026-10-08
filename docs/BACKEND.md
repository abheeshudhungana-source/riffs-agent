# RIFFs backend

The backend's chord-first slice parses chord symbols or Nashville numbers, builds a symbolic score, and exports MIDI, MusicXML, and Nashville chart JSON. WAV generation, model driven arrangement, persistence, and video processing remain open integrations.

## Run locally

Run these commands from the repository root:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app:app --reload
```

The API documentation is available at `http://127.0.0.1:8000/docs` while the server is running. The chord-first routes are mounted into the existing Day 0 FastAPI app.

## Parse a progression

Send `POST /api/v1/progressions/parse` with a progression string. Include `key` when using Nashville numbers; `tempo_bpm` is optional and defaults to 120.

```json
{
  "progression": "vi - IV - I - V",
  "key": "G major",
  "tempo_bpm": 110
}
```

The response includes each bar's source token, concert pitch root, chord quality, chord symbol, scale degree, and Nashville label when available. The example resolves to Em, C, G, D and the Nashville chart `| 6m | 4 | 1 | 5 |`.

Tempo is limited to 40–240 BPM, and progressions are limited to 32 bars in this initial API slice. The parser accepts major and minor keys, chord roots with sharps or flats, common chord qualities, and single-digit Nashville numbers or Roman numerals. The 32-bar limit is an initial request-size bound and can change with product requirements.

## Draft a symbolic score

`POST /api/v1/scores/draft` accepts the same request and returns a first score representation. This baseline assigns one chord to each 4/4 bar and represents its notes as MIDI pitches with beat timing and velocity. It uses block chords so the note data stays explicit; it does not add a groove or render audio.

For the G major example above, the response has four bars. The first bar is an Em chord with MIDI pitches 64, 67, and 71 (E minor triad), each starting at beat 0 and lasting four beats.

## Render symbolic exports

`POST /api/v1/tools/render-riff-to-audio` accepts the same request and returns a ZIP containing a MIDI file, MusicXML file, Nashville chord chart JSON, and a manifest. The manifest explicitly reports that WAV audio and the license certificate are unavailable until an audio renderer and licensed sample source are selected. The symbolic MIDI uses the current block-chord score, one chord per 4/4 bar.

For the G major example, the ZIP contains `riff_Gmaj_110bpm.mid`, `riff_Gmaj_110bpm.musicxml`, and `riff_Gmaj_110bpm_chord_chart.json`.

Run the unit tests from the repository root with `python -m unittest discover -s tests`.
