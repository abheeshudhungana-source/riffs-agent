# RIFFs backend PRD map

The PRD does not define an engineering milestone named Day 0 or Day 1. The Day 1 backend slice follows the latest pushed design: chord-first generation, register-tier instrument selection, chart data, symbolic MIDI lanes, and part locking.

## Implemented backend behavior

| PRD area | Backend behavior |
| --- | --- |
| Chord and Nashville input | Parses chord symbols, Nashville numbers, and Roman numerals when a key is supplied. |
| Chord-to-chart mapping | Returns chord symbols and Nashville labels using key and scale math. |
| Tempo validation | `/api/generate` accepts 60–200 BPM to match the practice UI. The versioned score/export routes accept 40–240 BPM. |
| Ensemble selection | Validates one to three supported instruments, at most one instrument per low/mid/high register, and rejects unsupported values. |
| Symbolic score | Produces MIDI note vectors and a MIDI file for each selected lane. |
| Role-specific lanes | `/api/generate` drafts distinct deterministic patterns for bass, chordal, melodic, and percussion roles; bass and lead use role-appropriate registers, percussion MIDI uses channel 10, and each lane reports its role. |
| Groove selection | `/api/generate` accepts `straight`, `half_time`, `swing`, or `half_time_shuffle`; absent an explicit selection, prompt wording selects a supported feel. The resolved groove and source are returned. |
| Part locking | When a requested locked lane exists in the previous take, the next take reuses that lane's exact note vectors and refreshes MIDI tempo metadata. The response includes note-vector and MIDI SHA-256 digests. |
| Take history | Writes immutable JSON take records to `~/.riffs-agent/takes` (or `RIFFS_TAKE_STORE_PATH`) and exposes `/api/takes/{storage_id}`. `base_storage_id` can seed the next take's locked lanes. |
| Versioned score/export API | Exposes progression parsing, score drafts, and a ZIP with MIDI, MusicXML, chord chart JSON, and a manifest. |
| Observable agent loop | Records observe/decide/act/observe history for parse, score, and symbolic export with a five-step cap; parse failures lead to a recorded clarification action. |
| Prompt safety baseline | Rejects explicit lyric/vocal, complete-song, and named exact-copy requests before score generation and optional LLM enrichment; returns a structured refusal and safe alternative. |
| Invalid input | Returns structured 422 responses for tempo, instrument selection, lock selection, and progression errors. |

The versioned symbolic score remains a simple chord-tone block arrangement: one chord per 4/4 bar. `/api/generate` now offers three deterministic role-specific groove presets, but it does not generate freeform AI-authored note variations. Guitar tablature remains a chord-shape preview rather than a full fingering engine.

## Not implemented or dependent on later decisions

| PRD area | Current gap |
| --- | --- |
| WAV/MP3 audio | WAV previews use deterministic oscillator synthesis and contain no sampled instruments. MP3 encoding and realistic sample libraries remain unconfigured. |
| License certificate | Provenance hashes are provided, but no rights grant or copyright clearance is issued. |
| Durable takes | Local JSON persistence survives local app restarts. Filesystem persistence on hosted/serverless deployments depends on the host's volume behavior and is not shared across instances. |
| Prompt-driven part regeneration | Prompt text resolves supported groove intent; richer freeform arrangement interpretation remains future work. |
| Melodic copyright detection | A transposition-invariant exact contour-window matcher runs when `RIFFS_MELODY_CORPUS` points to a JSON corpus. Without that configured reference set it reports `not_configured`; neither result is legal clearance. |
| Practice transport | Mute, metronome, speed trainer, and bar/beat transport remain client-side behavior. |
| Video dubbing | Requires upload handling, FFmpeg/ffprobe, isolated scratch storage, and enforcing the PRD's size/duration limits. |

## API routes

- `GET /api/health`
- `POST /api/generate` — frontend contract; returns chart data, per-lane MIDI, take ID, lock metadata, and license status.
- `POST /api/v1/progressions/parse`
- `POST /api/v1/scores/draft`
- `POST /api/v1/tools/render-riff-to-audio` — returns symbolic score/lane exports, a synthetic WAV preview, and a provenance manifest.
- `GET /api/takes/{storage_id}` — reads a locally persisted generated take.
