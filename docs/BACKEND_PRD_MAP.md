# RIFFs backend PRD map

The PRD does not define an engineering milestone named Day 0 or Day 1. The Day 1 backend slice follows the latest pushed design: chord-first generation, register-tier instrument selection, chart data, symbolic MIDI lanes, and part locking.

## Implemented backend behavior

| PRD area | Backend behavior |
| --- | --- |
| Chord and Nashville input | Parses chord symbols, Nashville numbers, and Roman numerals when a key is supplied. |
| Chord-to-chart mapping | Returns chord symbols and Nashville labels using key and scale math. |
| Tempo validation | `/api/generate` accepts 60–200 BPM to match the practice UI. The versioned score/export routes accept 40–240 BPM. |
| Ensemble selection | Validates one to three supported instruments, at most one instrument per low/mid/high register, and rejects unsupported values. |
| Symbolic score | Produces MIDI note vectors and a MIDI file for each selected lane. Low and high register lanes are transposed by an octave from the middle register. |
| Part locking | When a requested locked lane exists in the previous take, the next take reuses that lane's exact note vectors and refreshes MIDI tempo metadata. The response includes note-vector and MIDI SHA-256 digests. |
| Take history | Keeps the latest five generated takes in the running application process and assigns monotonically increasing take IDs. This is in-memory state, not durable storage. |
| Versioned score/export API | Exposes progression parsing, score drafts, and a ZIP with MIDI, MusicXML, chord chart JSON, and a manifest. |
| Invalid input | Returns structured 422 responses for tempo, instrument selection, lock selection, and progression errors. |

The symbolic score is still a simple chord-tone block arrangement: one chord per 4/4 bar. It does not yet generate role-specific grooves, voicings, or AI-authored note variations. Guitar tablature remains a chord-shape preview rather than a full fingering engine.

## Not implemented or dependent on later decisions

| PRD area | Current gap |
| --- | --- |
| WAV/MP3 audio | No audio renderer or licensed multisample source is configured. The frontend's Save MP3 control is still a UI placeholder. |
| License certificate | The API returns `status: not_issued`; it does not claim rights without a verified source and evidence. |
| Durable takes | Take history is process-local and will not survive a restart or reliably span serverless instances. A persistence choice is needed. |
| Part regeneration | The current symbolic baseline is deterministic and does not yet regenerate a musical role from the style prompt. |
| Practice transport | Mute, metronome, speed trainer, and bar/beat transport remain client-side behavior. |
| Video dubbing | Requires upload handling, FFmpeg/ffprobe, isolated scratch storage, and enforcing the PRD's size/duration limits. |

## API routes

- `GET /api/health`
- `POST /api/generate` — frontend contract; returns chart data, per-lane MIDI, take ID, lock metadata, and license status.
- `POST /api/v1/progressions/parse`
- `POST /api/v1/scores/draft`
- `POST /api/v1/tools/render-riff-to-audio` — returns symbolic files only; WAV generation and license certification are future work.
