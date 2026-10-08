# RIFFs backend PRD map

The PRD does not define a milestone named Day 0. This implementation treats Day 0 as the first usable backend foundation for the primary chord-first musician flow.

## Included in this Day 0 slice

| PRD area | Backend behavior |
| --- | --- |
| Typed chord and Nashville input | Parses chord symbols, Arabic Nashville numbers, and Roman numerals when a key is supplied. |
| Tempo | Accepts 40–240 BPM. |
| Note-first score | Builds one symbolic block chord per progression bar, with MIDI pitches, beat onset, duration, and velocity. |
| Chart data | Returns chord symbols and Nashville labels, and exports the chart as JSON. |
| Symbolic production handoff | Packages MIDI and MusicXML files with the chart JSON and a manifest in a ZIP. |
| Health check | Provides `GET /health`. |

The initial implementation assumes 4/4, one chord per bar, and a 32-bar limit. The PRD does not set a meter or progression-length limit, so these are provisional defaults.

## Still needed from product or infrastructure decisions

| PRD area | Current gap or dependency |
| --- | --- |
| Style prompt and arrangement generation | No model provider or arrangement schema has been selected. The current score is deterministic block chords, not generated drums, bass, or lead parts. |
| Sound matrix and instrument selection | The render request does not yet select or generate the PRD's instrument roles. |
| WAV stems and licensing certificate | Requires an audio renderer and licensed multisample source. The API manifest reports audio and certificate as unavailable; it does not create a certificate without evidence. |
| Part locking and take history | Requires generated instrument lanes and a persistence choice. |
| Practice state | Playback controls belong mainly in the client; server session behavior is not specified yet. |
| Guitar tablature | No guitar fingering or tablature mapping is implemented. |
| Video ingress and dubbing | Requires a video duration decision and FFmpeg/ffprobe integration. The PRD says 60 seconds in the tool constraints and 30 seconds in the latency metric. |
| Speed trainer | The PRD gives +2 to +5 BPM per clean loop and also +3 BPM in its architecture and eval example. |
| Hummed motif input | Mentioned as a product capability, but absent from the Stage 1 ingress specification. |

## Current API routes

- `GET /api/health` (provided by the Day 0 FastAPI app)
- `POST /api/v1/progressions/parse`
- `POST /api/v1/scores/draft`
- `POST /api/v1/tools/render-riff-to-audio` — currently produces symbolic exports only; WAV rendering and license certification are future work.
