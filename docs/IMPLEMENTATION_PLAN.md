# Final Implementation Plan: RIFFs (Musician Practice & Sketching Partner)

**Build Name:** RIFFs  
**Owners:** Abheeshu Dhungana & Michael Goslin  
**Date:** October 8, 2026  
**Status:** Ready for Execution (Post-Mara & Justin Peer Review)  

---

## 1. Executive Summary & Market Repositioning

Mara’s review (**"RIFFs: What Musicians Actually Need"**) delivers a crucial, evidence-backed reality check:
1. **The Market Has Moved:** In late 2026, claiming Suno is an "opaque black box" is obsolete—Suno Studio 2.0 added stem and MIDI export, and Apple Logic Pro 11 already ships realistic AI Session Players (drums, bass, keys).
2. **Our True Unfair Advantage:** RIFFs’ true defensible edge is that **the notes come first (the recipe before the cake)**. Because RIFFs generates symbolic scores before audio, our sheet music, tabs, and chord charts are **exact ground truth**, not noisy audio-to-MIDI guesses.
3. **Target Persona Focus:** We narrow our core focus to **Instrumentalists who practice and write** (Guitarists, Bassists, Keyboardists, Saxophonists), while preserving clean DAW handoff for producers and automated dubbing for content creators.

---

## 2. User Review Required

> [!IMPORTANT]
> **Market Narrative Update:** We are formally retiring the *"Suno is an un-editable black box and Guitar Pro is robotic MIDI"* narrative from all documentation and pitch scripts. We are repositioning RIFFs as:  
> **"The intelligent practice and sketching co-pilot that puts the player's ideas first, writes the notes before the audio, and gives working musicians exact charts and realistic accompaniment."**

> [!IMPORTANT]
> **Copyright & Licensing Overhaul:** We are replacing the rigid "3 consecutive intervals" detector with:
> 1. Multi-bar melodic contour matching (avoiding false positives on basic scales).
> 2. **Ethically Sourced Sample Guarantee + Export License Certificate** (verifiable proof of commercial clearance, inspired by Splice).

---

## 3. High-Impact Architecture Changes (Incorporating Mara's 8 Recommendations)

```
┌────────────────────────────────────────────────────────────────────────┐
│ 1. STAGE 1: CAPTURE & INPUT (Musician Stays the Author)                │
│    • Text Prompt (Genre/Vibe) OR                                       │
│    • Typed Chord Progression (e.g. "Am - F - C - G" / Nashville "1-4-5")│
│    • Hummed Audio / MIDI Pitch Ingestion (ScoreCloud pattern)          │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 2. STAGE 2: THE SYMBOLIC SCORE & PART-LOCKING HARNESS                  │
│    • Agent drafts complementary parts around the user's seed chords    │
│    • Part Locking: Lock bassline 🔒, regenerate drums & lead only     │
│    • Version History: Compare "Take 1" vs. "Take 2" non-destructively  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 3. STAGE 3: MULTI-VIEW NOTATION SUITE                                  │
│    • View 1: Working Musician's Chord Chart & Nashville Numbers (1-4-5)│
│    • View 2: 6-String Guitar Tablature (fret/string numbers)           │
│    • View 3: Traditional Five-Line Staff Sheet Music                   │
│    • View 4: Step-Sequencer Drum Grid View                             │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 4. STAGE 4: INTERACTIVE PRACTICE MODE                                  │
│    • Mute-Your-Part: Mute guitar to play along with the band           │
│    • Speed Trainer: Increments tempo by +3 BPM on each clean cycle     │
│    • Bar Loop: Highlight and loop a single difficult measure to drill  │
│    • Count-In: Audible 4-beat click pre-roll on every restart          │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 5. STAGE 5: PRODUCTION HANDOFF & HEADLESS CREATOR MUX                  │
│    • DAW Naming: `riff_Am_110bpm_bass.wav`, `riff_Am_110bpm.mid`       │
│    • Drag-and-Drop Stems & MusicXML score export                       │
│    • Provable License Certificate (`license_cert.json / .pdf`)         │
│    • Headless Video Dub (`attach_riff_to_video` for social creators)   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Proposed Technical Changes & Code Implementation

### Component 1: Ingress & Input Parsing
#### [NEW] `src/ingress/input_parser.py`
- Parse typed chord strings (e.g. `"Am - F - C - G"` or `"vi - IV - I - V"`) into structured diatonic harmonic roots.
- Convert simple audio/humming input into quantized MIDI note vectors via lightweight onset/pitch detection.

### Component 2: Part-Locking & Versioning Harness
#### [MODIFY] `src/harness/orchestrator_loop.py`
- Add `locked_tracks: List[str]` to the session state. If `locked_tracks = ["bass"]`, the agent preserves the bass note arrays verbatim and only generates variations for active lanes.
- Maintain a non-destructive take stack: `takes = [Take_01, Take_02, Take_03]`, allowing 1-click A/B toggling without losing earlier variations.

### Component 3: Multi-Format Chart & Notation Engine
#### [MODIFY] `src/notation/chart_generator.py`
- Generate three synchronized representations from the underlying score JSON:
  1. **Chord Chart & Nashville Numbers:** Compact grid with measure bars (`| Am | F | C | G |` or `| 1 | 4 | 1 | 5 |`).
  2. **Guitar Tabs:** 6-string fretboard layout.
  3. **Staff Notation:** Standard treble/bass clef MusicXML.
  4. **Drum Grid:** Step-sequencer matrix (Kick, Snare, Hi-Hat, Tom).

### Component 4: Practice Mode Web Audio Engine
#### [NEW] `src/audio/practice_engine.ts`
- **Solo / Mute Buttons:** Per-instrument mute allowing the player to silence their instrument and play along.
- **Speed Trainer:** Optional automatic tempo ramp-up (e.g., +2 to +5 BPM per loop cycle).
- **Single-Bar Looper:** Interactive start/end loop markers for drilling technical phrases.

### Component 5: Production Handoff & Licensing Sink
#### [MODIFY] `src/tools/render_riff_to_audio.py`
- Format stem filenames with metadata: `{project}_{key}_{bpm}bpm_{instrument}.wav`.
- Bundle a digital **Royalty-Free Commercial License Certificate** verifying that all audio derives from proprietary multisampled recordings and is cleared for distribution.
- Maintain the headless **`attach_riff_to_video`** utility for social creators.

---

## 5. Implementation Roadmap (Prioritized Sprints)

### Sprint 1 (Core MVP - The Musician Loop)
- [x] Symbolic score-first generation (notes before audio).
- [ ] Chord Progression input (`"Am F C G"` / Nashville numbers).
- [ ] Part-locking (lock bass/drums, regenerate lead).
- [ ] Mute-your-instrument practice playback with 4-beat count-in.
- [ ] Standardized DAW stem export naming (`riff_Am_120bpm_drums.wav`).

### Sprint 2 (Notation & Refinement)
- [ ] Nashville Number System toggle on the dashboard.
- [ ] Speed Trainer (incremental tempo ramping).
- [ ] License certificate generation on export.
- [ ] Headless video audio-replacement (`attach_riff_to_video`).

### Sprint 3 (Integrations & Plugins)
- [ ] Ableton Link tempo synchronization.
- [ ] Audio-to-MIDI humming capture.
- [ ] DAW VST3/AU plugin wrapper.

---

## 6. Verification & Testing Plan

### Automated Unit Tests
- `pytest tests/test_chord_parser.py`: Verify `"Am - Dm - G - C"` maps to correct MIDI root pitches.
- `pytest tests/test_part_locking.py`: Verify locked tracks remain byte-identical across multiple LLM mutation passes.
- `pytest tests/test_filename_convention.py`: Ensure all exported stems match `{key}_{bpm}bpm_{instrument}` schema.

### Musician Manual Verification Flow
1. **Input Test:** Type `"ii - V - I in C Major"` $\rightarrow$ Verify agent generates a jazz/bossa rhythm section matching those exact chords.
2. **Practice Test:** Click "Mute Saxophone" $\rightarrow$ Turn on Speed Trainer (+3 BPM) $\rightarrow$ Verify metronome counts in 4 beats, starts at 100 BPM, and accelerates cleanly to 103 BPM on bar 9.
3. **DAW Handoff Test:** Drag exported `.wav` stems directly into Logic / Ableton $\rightarrow$ Verify zero warping needed and file names display key/BPM cleanly.
