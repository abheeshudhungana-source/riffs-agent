# RIFFs: AI Practice & Sketching Partner for Musicians
## Design Feature & Architecture Review Document (Zero-Token-Waste Spec for Claude)

> **Context for Claude Sonnet 5.5 Analysis:**  
> This specification defines the finalized architecture, UI interaction flow, and data contract for **RIFFs** (Day 2 Milestone).  
> Analyze this document and provide strict, actionable technical output according to the instructions in **Section 5** with zero conversational filler.

---

## 1. Executive Summary & Non-Negotiable Boundaries

- **Core Philosophy:** "The Recipe Before the Cake" — Symbolic notes (MIDI, Nashville Numbers, Chord Progressions) are drafted **first** as ground-truth, and subsequently rendered into authentic acoustic multisamples.
- **Differentiator vs. Generative Audio (Suno/Udio):** We do not generate audio first and transcribe backward. Everything originates as verifiable symbolic notation.
- **Scope Restrictions:**
  1. Strictly instrumental riffs (No lyrics, no vocal synthesis).
  2. Copyright Guardrail: Refuses 1:1 reproductions of copyrighted commercial master recordings.
  3. Video Support: Strictly headless video audio-replacement (`attach_riff_to_video` via FFmpeg `-c:v copy -an`). No video editor UI.

---

## 2. Updated UI/UX Architecture & Layout Specifications

### 2.0. Top Header & HUD Navigation
- **HUD Items:** Key signature, Mode, BPM, and Take counter.
- **Dubbing & Editing Navigation Link:**
  - Placed on the top right next to the HUD controls.
  - A clean placeholder hyperlink (`🎬 Dubbing & Editing [Soon]`) leading to a dedicated separate future workspace/page, keeping the core looper canvas uncluttered.

### 2.1. Ingress & "Seed The Band" Flow (Day 2 Revision)
- **Problem with Day 0/1:** The "Seed The Band" card contained both the musical ingress (chords/Nashville) and a freeform style prompt input (`input-prompt`), cluttering the initial setup and confusing musicians who prefer structured input.
- **Approved Redesign:**
  1. **Minimalist "Seed The Band" Ingress:** The "Seed The Band" card is stripped down to bare musical ingress:
     - **Typed Chords or Nashville Numbers Input** (e.g., `Am - F - C - G` or `1 - 4 - 5 - 1`).
     - **Action Trigger:** Immediate "✨ Generate Riff & Backing Track" button.
     - *(Note: Freeform prompt is modalized, video dropzone is moved to the top-right page, and instrument ensemble configuration is relocated into Section 2: Musician Practice Suite).*
  2. **[PROPOSED / BRACKETED FEATURE: Prompt Modal / Pop-Up on Action]**
     > *Note: This feature is currently bracketed [ ] for evaluation. Claude should review this as a pending enhancement without making breaking assumptions.*
     - Clicking **"✨ Generate Riff & Backing Track"** triggers a focused, modal pop-up (or slide-over drawer).
     - The modal captures the nuanced stylistic intent:
       - Style / Vibe prompt (e.g., *"Funky neo-soul pocket with driving bass"*).
       - Genre & Groove Presets (tags: *Neo-Soul, Halftime Shuffle, Indie Rock, Lo-Fi, Walking Bass*).
       - Tempo (BPM) & Key confirmation.
       - Direct "Confirm & Synthesize" action button.

### 2.2. Interactive Multi-Format Notation Deck (Triple-View)
Musicians do not solely read 5-line staff notation. The UI must toggle dynamically between:
1. **View A — Nashville Number Lead Sheet:**
   - Displayed as high-contrast measure bars: `| 1m | 4 | 1 | 5 |`.
   - Allows instant mental transposition across keys without recalculating fret positions.
2. **View B — 6-String Guitar Tablature:**
   - Fretboard coordinates ($E, A, D, G, B, e$) with rhythmic markers.
   - Synchronized active playhead cursor during looper playback.
3. **View C — Traditional 5-Line Staff Notation:**
   - Clef, key signature, noteheads, and measure divisions.

### 2.3. The Musician Practice Suite (Interactive Loop Engine & Ensemble Setup)
- **Practice Ensemble Setup (Relocated Instrument Tier Dropdowns):**
  - **Low End (Sub/Bass):** Dropdown containing *Bass Guitar, Contrabass, Bass Drums, Floor Tom, None (Off)*.
  - **Mid End (Body):** Dropdown containing *Rhythm Guitar, Acoustic Piano, Tenor Sax, Bongos, None (Off)*.
  - **High End (Top/Air):** Dropdown containing *Cymbals, Ukulele, Piccolo, Triangle, None (Off)*.
- **Speed Trainer:** Checkbox toggle for auto-ramping tempo (`+3 BPM` per 8-bar loop).
- **Mute-Your-Part Tier Controls (Hardware-style LED Kill Switches):**
  - Dedicated hardware-style toggle buttons for each register tier (**Low**, **Mid**, **High**).
  - Normal state displays neutral `LIVE` with dark LED.
  - When pressed, activates an active audio kill: turns label to bold `MUTED` and triggers an urgent glowing red warning LED dot (`shadow-[0_0_8px_rgba(244,63,94,0.9)]`), providing instant tactile visual feedback for live play-along.
- **Count-In Pre-Roll & Metronome (Hardware-style LED Toggle):**
  - Metronome button equipped with an interactive glowing green LED indicator dot (`shadow-[0_0_8px_rgba(52,211,153,0.9)]`) and toggle state (`ON` / `OFF`), providing instant visual confirmation of metronome active state.
  - 4-beat woodblock metronome count-in before loop initiation.

### 2.4. Playback, Transport & Groove Bar (Neo-Soul Groove Architecture)
- **Symmetric Centered Transport Bar:**
  - **Left Section:** Groove Title (`Neo-Soul Groove`) & active Bar/Beat counter (`Bar: 1/8 • Beat: 1`).
  - **Center:** Prominent, large Play/Pause hardware trigger (`w-14 h-14` emerald glowing button) as the focal point.
  - **Right Section:** Compact Tempo/BPM slider ($60 \to 200$, $4/4$ Metre) alongside non-destructive Take selector tabs (`T1`, `T2`, `T3`).
  - **Lower Deck:** 8-bar loop visual step grid and Track Lanes with individual Part-Locking switches (🔒 / 🔓).

---

## 3. Data Contract & Backend Integration

### 3.1. API Endpoints (FastAPI)
- `GET /`: Serves the interactive dashboard.
- `GET /api/health`: Service health, model identification, and API key configuration status.
- `POST /api/generate`:
  ```json
  {
    "prompt": "Funky neo-soul pocket with driving bass",
    "key": "Am",
    "bpm": 110,
    "chords": "Am - F - C - G",
    "instruments": ["drums", "bass", "saxophone"],
    "locked_parts": ["bass"]
  }
  ```

### 3.2. Response Contract
```json
{
  "status": "success",
  "data": {
    "key": "Am",
    "bpm": 110,
    "nashville_chart": ["1m", "4", "1", "5"],
    "tab_score": "e|---0-------1-------0-------3---|...",
    "stems": [
      {"lane": "bass", "filename": "riff_Am_110bpm_bass.wav", "locked": true},
      {"lane": "drums", "filename": "riff_Am_110bpm_drums.wav", "locked": false}
    ],
    "license_certificate": {
      "license_id": "CERT-RIFFS-2026-X892",
      "status": "100% Royalty-Free Multisample Acoustic Engine"
    }
  }
}
```

---

## 4. Immediate Architectural Decisions to Finalize

1. **Modal UX Details:**
   - Should the "Generate Riff" pop-up also allow instant re-prompting while preserving the currently locked tracks without closing the modal?
2. **Audio Sync Timing:**
   - Web Audio API vs. Tone.js for the in-browser looper and Speed Trainer clock accuracy.
3. **Streamlined Audio Export (Save MP3):**
   - Replaced complex multi-track DAW zip handoffs with a simple, high-fidelity **"Save MP3"** export.
   - Users can instantly download the master mix of their generated accompaniment as a 320kbps MP3 for practice on any phone or music player.

---

## 5. Instructions for Claude Sonnet 5.5

When reviewing this specification, produce **only** the following three deliverables:

1. **Deliverable 1: UI Component Tree & Modal Interaction Spec**
   - Provide the clean HTML/Tailwind structure for removing the inline prompt input and replacing it with the Generate Modal/Drawer.
2. **Deliverable 2: Frontend State Machine (TypeScript/JavaScript schema)**
   - Exact client-side state schema tracking `currentTake`, `lockedTracks`, `modalOpen`, `bpm`, and `speedTrainerActive`.
3. **Deliverable 3: Error & Boundary Handling Table**
   - Exact UI behavior for:
     - Selecting 0 or $>3$ instruments.
     - Uploading a video $>50$MB or unsupported codec.
     - Inputting invalid chord strings or impossible Nashville numbers.
