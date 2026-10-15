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

The frontend uses `POST /api/generate`. It accepts `prompt`, `key`, `bpm`, `chords`, `instruments`, `locked_parts`, and an optional `groove` preset. Supported grooves are `straight` (the default), `half_time`, and `swing`. The endpoint enforces the practice UI's 60–200 BPM range, validates the selected register tiers, and returns Nashville chart data plus per-lane symbolic notes and MIDI bytes.

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

Each successful response includes a monotonically increasing `take_id`, the chosen top-level `groove`, `part_scores`, and the compatibility `stems` field. Each part score also reports its groove. Despite the legacy `stems` field name, each listed file is symbolic MIDI (`.mid`), not a rendered audio stem. `part_scores[instrument].midi_base64` contains its file, `midi_sha256` identifies the exact file bytes, and `note_vector_sha256` identifies the note data independently of tempo. When a lane is locked and was present in the previous take, the backend keeps its exact prior note vectors and reports the groove stored with that lane while refreshing MIDI tempo metadata. Swing note timing uses triplet subdivisions. The latest five takes are kept in memory for the lifetime of the app process only.

The `license_certificate` response is explicitly marked `not_issued`. The current repo does not configure a licensed sample source, and neither the `/api/generate` route nor the frontend Save MP3 button produces WAV/MP3 audio. The versioned render route remains the supported way to download symbolic MIDI, MusicXML, and chord-chart exports.

Generation requests reject unknown fields, including the removed `issue_license` flag. `/api/generate` and `/api/vocals/approve` require a signed bearer token with the `beta_tester` role and `generation` entitlement. Configure `RIFFS_JWT_SECRET` (at least 32 random bytes), `RIFFS_JWT_ISSUER`, and `RIFFS_JWT_AUDIENCE`; tokens must use HS256 and include `sub`, `exp`, `iss`, `aud`, `roles`, and `entitlements`. Missing or invalid configuration fails closed. Each subject is limited to 10 requests per fixed 60-second window across app instances. Set `REDIS_URL` to the shared Redis service; generation returns 503 if Redis is unavailable.

The versioned `/api/v1/scores/draft` and symbolic package export remain chord-first, with one block chord per bar. `/api/generate` now expands that chord draft into role-specific symbolic lanes, but does not yet derive variations from the style prompt. See [BACKEND_PRD_MAP.md](BACKEND_PRD_MAP.md) for the scope boundary and remaining PRD work.

## Instrument role patterns

`POST /api/generate` turns the chord draft into a deterministic note pattern for each selected lane. The explicit groove preset changes rhythmic density and timing for bass, chordal, melodic, and percussion roles. Bass lanes use root/fifth patterns, chordal instruments play stabs, melodic instruments use chord tones, and percussion lanes use General MIDI drum pitches on MIDI channel 10. Each `part_scores` entry and `stems` item includes its `role`; each part score also reports its groove. Freeform prompt text still does not select or alter the groove automatically.

## Prompt safety foundation

`POST /api/generate` checks the user's creative prompt before score generation or an optional model call. Lyrics are available only through the explicit `lyrics_prompt` flow: the first response returns a draft and a human-approval checkpoint without a vocal lane. The approval token is signed over the creative request fields and exact draft, expires after ten minutes, and is atomically consumed once in shared Redis. Set `RIFFS_VOCAL_SECRET` to a random value of at least 32 bytes; without it, vocal approval fails closed with a generic unavailable response. Redis must also be configured for approval consumption; Redis errors fail closed. Edited lyrics are validated and receive a new checkpoint, so the user must review and approve the revised text separately. Complete-song and explicit exact or verbatim copying requests remain refused. Structured `riffs_vocal_trace` log records include the correlation ID, fingerprints, stage, and decision reason, but never raw tokens or lyric text.

These checks are a deterministic ingress baseline, not a musical copyright detector. The current backend has no melodic hook corpus, multi-bar contour comparison, or licensed sample catalog, and the block-chord score cannot establish whether a generated melody resembles a commercial recording. Do not interpret a request passing these checks as a clearance result.

## Observable symbolic agent loop

`POST /api/v1/agent/run` records each observation, state-based decision, action result, and post-action observation while parsing a progression, drafting a score, and exporting the symbolic package. An optional prompt is checked before parsing; an unsafe request is observed as `unsafe_request`, then the policy records a `refuse` action and ends in `refused` without drafting. A parse failure is observed as `parse_failed`; the policy then records a `request_clarification` action and ends in `awaiting_input`. The route caps the loop at five steps. Its policy is deterministic and does not use an LLM.
