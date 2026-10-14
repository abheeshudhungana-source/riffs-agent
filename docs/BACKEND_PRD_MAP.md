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
| Groove selection | `/api/generate` accepts `straight`, `half_time`, or `swing`; the selected preset changes role-specific timing and note density. Locked lanes retain their prior notes and groove. Freeform prompt text does not automatically select a groove. |
| Part locking | When a requested locked lane exists in the previous take, the next take reuses that lane's exact note vectors and refreshes MIDI tempo metadata. The response includes note-vector and MIDI SHA-256 digests. |
| Take history | Keeps the latest five generated takes in the running application process and assigns monotonically increasing take IDs. This is in-memory state, not durable storage. |
| Versioned score/export API | Exposes progression parsing, score drafts, and a ZIP with MIDI, MusicXML, chord chart JSON, and a manifest. |
| Observable agent loop | Records observe/decide/act/observe history for parse, score, and symbolic export with a five-step cap; parse failures lead to a recorded clarification action. |
| Prompt safety baseline | Rejects explicit lyric/vocal, complete-song, and named exact-copy requests before score generation and optional LLM enrichment; returns a structured refusal and safe alternative. |
| Invalid input | Returns structured 422 responses for tempo, instrument selection, lock selection, and progression errors. |

The versioned symbolic score remains a simple chord-tone block arrangement: one chord per 4/4 bar. `/api/generate` now offers three deterministic role-specific groove presets, but it does not generate freeform AI-authored note variations. Guitar tablature remains a chord-shape preview rather than a full fingering engine.

## Not implemented or dependent on later decisions

| PRD area | Current gap |
| --- | --- |
| WAV/MP3 audio | No audio renderer or licensed multisample source is configured. The frontend's Save MP3 control is still a UI placeholder. |
| License certificate | The API returns `status: not_issued`; it does not claim rights without a verified source and evidence. |
| Durable takes | Take history is process-local and will not survive a restart or reliably span serverless instances. A persistence choice is needed. |
| Prompt-driven part regeneration | Groove can be selected explicitly, but role patterns do not yet infer a groove or other arrangement changes from freeform style text. |
| Melodic copyright detection | No multi-bar contour matcher or hook database is configured; passing prompt checks is not a copyright clearance. The `/api/generate` lead line is a deterministic chord-tone pattern, not a style-generated melody. |
| Practice transport | Mute, metronome, speed trainer, and bar/beat transport remain client-side behavior. |
| Video dubbing | Requires upload handling, FFmpeg/ffprobe, isolated scratch storage, and enforcing the PRD's size/duration limits. |

## API routes

- `GET /api/health`
- `POST /api/generate` — frontend contract; returns chart data, per-lane MIDI, take ID, lock metadata, and license status.
- `POST /api/v1/progressions/parse`
- `POST /api/v1/scores/draft`
- `POST /api/v1/tools/render-riff-to-audio` — returns symbolic files only; WAV generation and license certification are future work.
