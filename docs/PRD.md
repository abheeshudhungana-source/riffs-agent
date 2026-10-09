# Product Requirements Document: RIFFs

**Build Name:** RIFFs (AI Practice & Sketching Partner for Musicians)  
**Owners:** Abheeshu Dhungana & Michael Goslin  
**Date:** October 8, 2026  
**Status:** Approved & Finalized (Incorporating Mara & Justin Peer Reviews)  

---

## 1. Problem Statement
Instrumentalists who practice and write (guitarists, bassists, keyboardists, saxophonists) and independent creators face a fragmented musical workflow:
1. **The Ideas Get Lost in Voice Memos:** Songwriters accumulate hundreds of phone voice memos that cannot be searched, transposed, or converted into editable backing tracks.
2. **Audio-First AI Jukeboxes Guess the Notes:** Generative AI tools (like Suno) generate audio first and estimate notes afterward, leading to inaccurate sheet music and messy, artifact-laden stem separations.
3. **Existing Practice Tools Only Work on Old Songs:** Practice apps (like Moises) can slow down or isolate stems from existing commercial music, but offer nothing original for players to write over or legally distribute.
4. **The Friction of Studio Charting:** Working musicians and session players don't read traditional 5-line staff notation—they read chord charts and the Nashville Number System. Current AI tools produce none of these.

**The Solution:** **RIFFs** writes **the notes first (the recipe before the cake)**, then renders them using authentic recordings of real instruments. Because symbolic notes drive the engine:
- Sheet music, guitar tabs, and Nashville number chord charts are **exact ground truth**, not guessed from audio.
- Instrumentalists can **input their own ideas** (typing chords like `"Am - F - C - G"` or humming a motif), lock parts they love, drill tricky phrases in **Practice Mode**, and export DAW-ready stems with **verifiable royalty-free licensing certificates**.
- For social creators, RIFFs includes a headless video audio-replacement tool (`attach_riff_to_video`) that dubs the custom riff onto raw video clips in under 1.5 seconds with zero video-editing software.

---

## 2. Competitive Positioning

| Feature / Dimension | **Suno Studio 2.0** | **Logic Pro 11 Session Players** | **Guitar Pro 8** | **RIFFs** (Our Product) |
| :--- | :--- | :--- | :--- | :--- |
| **Note-First Architecture** | ❌ No (Audio first; MIDI is guessed via extraction). | ⚠️ Partial (Follows chords; limited instrument set). | ✅ Yes (Manual score entry; no AI generation). | **✅ Core Architecture (Notes drafted first $\rightarrow$ drives audio).** |
| **Input Options** | Text prompts only. | Chord track in Logic timeline. | Manual mouse/keyboard note entry. | **Text prompt, typed chords, Nashville numbers, or hummed pitch.** |
| **Working Musician Charts** | ❌ None. | ❌ None. | ⚠️ Tab & staff notation (No Nashville numbers). | **Triple-View: Chord Charts (Nashville 1-4-5), 6-String Tab, & Sheet Music.** |
| **Part Locking & Takes** | ❌ Regenerates entire audio. | ✅ Complexity & intensity sliders. | N/A (Manual editor). | **Part-Locking (lock bass 🔒, re-roll drums) + Non-destructive take stack.** |
| **Built-in Practice Suite** | ❌ None. | ❌ None. | ⚠️ Metronome only. | **Speed Trainer (+3 BPM auto-ramp), part-muting, & single-bar looper.** |
| **Licensing Assurance** | ⚠️ Model trained on commercial catalogs (settled lawsuits). | ✅ Royalty-free Apple loops. | N/A (User creates content). | **Verifiable License Certificate bundled with every export.** |

---

## 3. Product Scope & Functional Taxonomy

### 3.1. Target Personas
1. **Primary: Instrumentalists Who Practice & Write** (Guitar, Bass, Keys, Sax): Need custom, in-key backing tracks at their own speed with accurate chord charts and tabs.
2. **Secondary: Songwriters & Producers:** Want to turn chord sketches into multi-track arrangements with clean DAW drag-and-drop.
3. **Tertiary: Short-Form Video Creators:** Need instant, royalty-safe background music dubbed directly to phone clips without opening video editors.

### 3.2. Musical Capture & Ingress (Stage 1: Seed The Band)
- **Typed Chord Progression:** Accepts standard chord names (`Am - Dm - G - C`) or Nashville Numbers (`1 - 4 - 5 - 1`).
- **Streamlined Action Trigger:** Generates accompaniment directly from chord foundation without inline clutter.
- **Dedicated Dubbing Navigation:** Video dubbing is decoupled to a dedicated top-right workspace (`🎬 Dubbing & Editing`), keeping the core practice canvas clean and focused.

### 3.3. Sound Matrix & Practice Ensemble Setup (3 Registers $\times$ 3 Functional Roles)
Users configure their practice band via Tier Dropdown Selectors located directly inside the Practice Suite:

| Sound Tier | Percussion Options | Rhythm Options | Lead Options |
| :--- | :--- | :--- | :--- |
| **Low End** (Sub / Bass) | Bass drums, Floor tom | Bass guitar, Contrabass | — |
| **Medium End** (Core Body) | Bongos | Rhythm guitar, Acoustic piano | Tenor saxophone |
| **High End** (Top / Air) | Cymbals, Triangle | Ukulele | Piccolo |

### 3.4. Practice Mode & Playback Suite (Hardware Studio Feel)
- **Practice Ensemble Setup:** Dynamic dropdowns for Low End, Mid End, and High End instrument selection.
- **Hardware-Style LED Mute Switches:** Dedicated kill-switch buttons for each tier (**Mute Low**, **Mute Mid**, **Mute High**) with active red glowing warning LEDs (`MUTED` state) for seamless live play-along.
- **Metronome with Green LED Indicator:** Hardware-style ON/OFF toggle with glowing emerald LED.
- **Speed Trainer:** Checkbox toggle auto-incrementing tempo by $+3$ BPM after each clean 8-bar loop iteration.
- **Symmetric Transport Bar:** Centered, prominent ▶ Play/Pause trigger, live Bar ($1 \to 8$) & Beat ($1 \to 4$) tracking, inline Tempo slider ($60 \to 200$ BPM, 4/4 Metre), and non-destructive Take selector (`T1`, `T2`, `T3`).

### 3.5. Multi-Format Notation Dashboard
- **View A: Chord Chart & Nashville Numbers:** Clean, high-contrast lead sheet showing measure bars (`| 1 | 4 | 5 | 1 |`) for instant transposing.
- **View B: 6-String Guitar Tablature:** String and fret numbering with follow cursor.
- **View C: Staff Sheet Music:** Traditional 5-line notation.

### 3.6. Part-Locking & Versioning (Replacing One-Shot Edits)
- **Part Lock:** Users can click a lock icon (🔒) on any lane (e.g., keep the bassline) and prompt the agent to regenerate only companion lanes, preserving symbolic MIDI byte-fidelity.
- **Take History:** Preserves the last 5 iterations as selectable tabs (`Take 1`, `Take 2`, `Take 3`).

### 3.7. Audio Export & Delivery
- **Save MP3:** Immediate, frictionless download of the generated accompaniment riff as high-quality 320kbps MP3 for practice across mobile and desktop devices.
- **Headless Video Dubbing (`attach_riff_to_video`):** Accessible via dedicated Dubbing & Editing workspace; strips camera audio and remuxes the riff into a clean MP4 in $< 1.5$ seconds (strictly **no video player or editor UI**).

---

## 4. System Architecture & Tool Suite

```
       ┌────────────────────────────────────────────────────────┐
       │             User Ingress & Capture Engine              │
       │   - Typed Chords ("Am - F - C - G" / Nashville "1-4-5")│
       │   - Optional: Upload raw clip (skate.mp4)              │
       └───────────────────────────┬────────────────────────────┘
                                   │
                                   ▼
             ┌───────────────────────────────────────────┐
             │            Agent Harness Loop             │
             │   - Tracks Iterations (Max 5 turns)       │
             │   - Enforces Locked Tracks (🔒 Bass)       │
             │   - Swappable LLMs (Gemini / GPT-4o)      │
             └─────────────────────┬─────────────────────┘
                                   │
                                   ▼
             ┌───────────────────────────────────────────┐
             │       Symbolic Score & Licensing Gate     │
             │   - Generates Notes, Velocities, Chords   │
             │   - Scans Melodic Contours vs Hook DB     │
             └─────────────────────┬─────────────────────┘
                                   │
                                   ▼
             ┌───────────────────────────────────────────┐
             │        Tool 1: render_riff_to_audio       │
             │   - Multisample Acoustic Synthesis        │
             │   - Produces Stems, MIDI, MusicXML        │
             │   - Emits License Certificate             │
             └─────────────────────┬─────────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │                             │
    [Audio / Practice Mode]                       │ [Video Uploaded]
                    ▼                             ▼
┌───────────────────────────────┐   ┌───────────────────────────────┐
│     Musician Practice Suite   │   │ Tool 2: attach_riff_to_video  │
│ - Speed Trainer (+3 BPM ramp) │   │ - Headless FFmpeg remux       │
│ - Mute-Your-Part Playalong    │   │ - Strips mic noise (-an)      │
│ - Chord Charts & Nashville    │   │ - Stream copy (-c:v copy)     │
│ - DAW Drag-and-Drop (.wav)    │   └─────────────┬─────────────────┘
└───────────────────────────────┘                 │
                                                  ▼
                                    ┌───────────────────────────────┐
                                    │    Export Finished Video      │
                                    │  (Ready for TikTok / Reels)   │
                                    └───────────────────────────────┘
```

---

## 5. Tool Specifications & Blast Radius

| Tool Name | Type | Input Constraints & Safeguards | Execution |
| :--- | :--- | :--- | :--- |
| **`render_riff_to_audio`** | Symbolic & Audio Synthesis | • Max 3 active instruments.<br>• Tempo constrained to $40\le \text{BPM} \le 240$.<br>• Respects `locked_tracks` array.<br>• Generates verifiable `license_cert.json`. | Outputs isolated WAV stems, MIDI, MusicXML, and Nashville chord chart JSON. |
| **`attach_riff_to_video`** | Headless Remux | • Max video file size: **50 MB**.<br>• Max video duration: **60 seconds**.<br>• Format whitelist: `.mp4`, `.mov`.<br>• Isolated ephemeral scratch space. | Runs `-c:v copy` remux without re-encoding video frames in $< 1.5\text{s}$. |

---

## 6. Eval Cards & Test Fixtures

### Case 1: The Songwriter Golden Path (Chord-First Ingress)
* **Input:** User types: `"Chord progression: vi - IV - I - V in G Major, 110 BPM. Add a pocket drum groove and walking bass."`
* **Expected Output:**
  * Ingress parser maps Nashville numbers to `Em - C - G - D`.
  * Agent drafts drums and bass locked to that progression.
  * Outputs Nashville Chord Chart view (`| 6m | 4 | 1 | 5 |`), Tab, and audio stems.
  * Stems exported as `riff_Gmaj_110bpm_drums.wav` and `riff_Gmaj_110bpm_bass.wav`.

### Case 2: Practice Mode & Part-Locking
* **Input:** User locks bass (`locked_tracks = ["bass"]`), turns on "Speed Trainer (+3 BPM)", and prompts: *"Make the drums play a halftime shuffle instead."*
* **Expected Output:**
  * Bassline MIDI note vectors remain 100% byte-identical to prior take.
  * Drum lane regenerates with shuffle timing.
  * Speed trainer increments tempo from 110 to 113 BPM on loop cycle 2.
  * Take 1 and Take 2 are both preserved in the take history.

### Case 3: Adversarial / Video Mux Boundary
* **Input:** User uploads a 150MB `.mov` file with string injection in the filename: `"test; rm -rf /; ignore_rules.mov"`.
* **Expected Output:**
  * File size validator intercepts payload at ingress ($> 50\text{MB}$ limit).
  * Sanitizer strips shell metacharacters from filename.
  * Tool aborts cleanly with: *"File exceeds 50MB limit. Please upload an MP4 or MOV under 50MB."*

---

## 7. Success Metrics & KPIs
- **Chord-to-Chart Latency:** $\le 800\text{ms}$ to parse typed chords into interactive Nashville/Tab charts.
- **DAW Sync Accuracy:** $0\text{ms}$ drift when stems are dragged onto Ableton/Logic grid.
- **Practice Engagement:** $\ge 70\%$ of test instrumentalists use the Speed Trainer or Part-Mute toggle during practice sessions.
- **Video Remux Latency:** $\le 1.5\text{s}$ for videos up to 30s.
