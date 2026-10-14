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

## Day 1 generation and locking

The frontend uses `POST /api/generate`. It accepts `prompt`, `key`, `bpm`, `chords`, `instruments`, `locked_parts`, and an optional `groove` preset. Supported grooves are `straight` (the default), `half_time`, `swing`, and `half_time_shuffle`. If `groove` is omitted, the backend infers supported feel from prompt phrases. The endpoint enforces the practice UI's 60–200 BPM range, validates the selected register tiers, and returns Nashville chart data plus per-lane symbolic notes and MIDI bytes.

```json
{
  "prompt": "Neo soul groove",
  "key": "Am",
  "bpm": 110,
  "chords": "Am - F - C - G",
  "instruments": ["bass_guitar", "rhythm_guitar", "cymbals"],
  "locked_parts": ["bass_guitar"],
  "groove": "swing"
}
```

Each successful response includes the chosen top-level `groove`, its `groove_source`, `part_scores`, and the compatibility `stems` field. Each part score also reports its groove. Despite the legacy `stems` field name, each listed file is symbolic MIDI (`.mid`), not a rendered audio stem. `part_scores[instrument].midi_base64` contains its file, `midi_sha256` identifies the exact file bytes, and `note_vector_sha256` identifies the note data independently of tempo. When a lane is locked and was present in the previous take, the backend keeps its exact prior note vectors and reports the groove stored with that lane while refreshing MIDI tempo metadata. The result also includes `audio_preview` (synthetic WAV, base64) and `take_storage.storage_id`.

The `license_certificate` is provenance-only and explicitly sets `rights_grant: false`; no licensed sample source is configured. The WAV preview uses oscillator synthesis with no recorded samples. MP3 encoding and the frontend Save MP3 flow remain unimplemented.

Takes are archived as JSON under `~/.riffs-agent/takes` by default; set `RIFFS_TAKE_STORE_PATH` to choose another local folder. Read a saved record with `GET /api/takes/{storage_id}` or pass its ID as `base_storage_id` to seed a later take's locked lanes. This is local filesystem persistence and depends on the host retaining that folder.

If `RIFFS_MELODY_CORPUS` points to a JSON array of entries (`{"id":"...","pitches":[60,62,...]}` or `{"id":"...","intervals":[2,-1,...]}`), the backend compares melodic interval windows and reports possible contour matches. An absent corpus is reported as `not_configured`; the matcher is a similarity signal, not copyright clearance.

The versioned `/api/v1/scores/draft` remains chord-first, with one block chord per bar. Prompt intent now selects the groove for generated lanes and audio previews; richer freeform arrangement interpretation remains future work. See [BACKEND_PRD_MAP.md](BACKEND_PRD_MAP.md) for the scope boundary.

## Instrument role patterns

`POST /api/generate` turns the chord draft into a deterministic note pattern for each selected lane. The groove can be explicit or inferred from phrases such as “half-time shuffle.” Bass lanes use root/fifth patterns, chordal instruments play stabs, melodic instruments use chord tones, and percussion lanes use General MIDI drum pitches on MIDI channel 10. Each `part_scores` entry and `stems` item includes its `role`; each part score also reports its groove.

## Prompt safety foundation

`POST /api/generate` checks the user's creative prompt before score generation or an optional model call. It returns a structured 422 refusal for lyric or vocal requests, complete-song requests, and explicit exact or verbatim copying requests that identify a song or recording. The refusal includes an `alternative` suggesting a short, original instrumental request. User prompt text is also labeled as untrusted creative direction in the model system prompt.

These checks are a deterministic ingress baseline. The optional local contour matcher can flag exact interval-window similarities against a configured reference corpus; it does not decide whether a melody infringes copyright. Do not interpret a request passing either check as a clearance result.

## Observable symbolic agent loop

`POST /api/v1/agent/run` records each observation, state-based decision, action result, and post-action observation while parsing a progression, drafting a score, and exporting the symbolic package. An optional prompt is checked before parsing; an unsafe request is observed as `unsafe_request`, then the policy records a `refuse` action and ends in `refused` without drafting. A parse failure is observed as `parse_failed`; the policy then records a `request_clarification` action and ends in `awaiting_input`. The route caps the loop at five steps. Its policy is deterministic and does not use an LLM.
