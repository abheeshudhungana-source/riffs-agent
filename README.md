# RIFFs: Autonomous Music Theory & Acoustic Sketching Co-Producer

[![CI / Regression Tests](https://img.shields.io/badge/tests-114%20passed-emerald)](https://github.com/abheeshudhungana-source/riffs-agent)
[![Live Demo](https://img.shields.io/badge/live%20demo-riffs--agent.vercel.app-blue)](https://riffs-agent.vercel.app)
[![Python](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11-indigo)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-slate)](LICENSE)

**Repository:** [https://github.com/abheeshudhungana-source/riffs-agent](https://github.com/abheeshudhungana-source/riffs-agent)  
**Live Production URL:** [https://riffs-agent.vercel.app](https://riffs-agent.vercel.app)  
**Owners:** Abheeshu Dhungana & Michael Goslin  
**Milestone:** Final Build Submission  

---

## 🎯 Role & Industry

* **Role:** Autonomous Music Theory & Acoustic Sketching Co-Producer.
* **Industry:** Music Technology, Songwriting Tools, and Musician Practice & Education.
* **Target Users:** Working musicians, songwriters, educators, and instrumentalists who need an interactive, editable practice band that respects the craft of music theory.
* **The Problem Solved:** Songwriters and practicing musicians currently face an unappealing binary choice: static, mechanical chord backing apps (e.g. iReal Pro) that cannot compose new parts or generate lyrical concepts, or black-box generative AI audio tools (e.g. Suno, Udio) that spit out flattened, uneditable audio waveforms with no chord charts, no guitar tabs, and no stems. RIFFs bridges this gap as an autonomous co-producer that outputs structured, multi-track symbolic scores that musicians can learn, transpose, edit, and play along with in real time.
* **Core Philosophy:** **"The Recipe Before the Cake"** — Symbolic musical notation (Nashville Numbers, Guitar Tablature, Multi-track MIDI) is composed and verified *first*, and subsequently rendered into authentic acoustic sound. Unlike black-box audio diffusion models, every single note, chord degree, and lyric event remains 100% inspectable, editable, and lockable.

---

## 🚀 What the Agent Does

1. **Dual-Prompting Architecture (Suno-style Workflow with Theoretical Grounding):**
   * **Prompt 1 (Instrumental & Groove):** Seed the band with chord progressions (e.g. `Am - F - C - G`), Nashville Numbers (e.g. `1m - b6 - b3 - b7`), tempo (60–200 BPM), and style direction (e.g. *"Funky neo-soul pocket with driving bass"*).
   * **Prompt 2 (Lyrics & Vocal Studio):** Prompt for theme, rhyme structure, vocal style (*soulful lead, pop lead, rap lead, folk lead*), and language (*English, Spanish, French, Japanese*).

2. **Human-in-the-Loop (HITL) Vocal Checkpoint:**
   * The agent halts before voice synthesis and issues a cryptographic, time-limited HMAC token (`awaiting_vocal_confirmation`).
   * The musician reviews the 4-line verse, optionally edits lines bar-by-bar, and acknowledges rights before authorizing vocal synthesis.
   * Approval tokens cryptographically bind the request context, exact lyric text hash, and expiration timestamp to prevent tampering or replay attacks.

3. **Multi-Format Interactive Notation Deck:**
   * **Nashville Number Lead Sheet:** Dynamic cards displaying chord scale degrees for instant transposition across any key without mental recalculation.
   * **6-String Guitar Tablature:** Real-time synced fretboard coordinates ($E, A, D, G, B, e$) with rhythmic position markers.
   * **Lyrics & Chord Lead Sheet:** Bar-by-bar aligned verse display with active playhead highlighting.

4. **Multi-Track Arrangement & Non-Destructive Part-Locking:**
   * Three-tier acoustic ensemble: **Low End** (Bass Guitar, Contrabass, Bass Drums, Floor Tom), **Mid End** (Rhythm Guitar, Acoustic Piano, Tenor Sax, Bongos), **High End** (Cymbals, Ukulele, Piccolo, Triangle), plus **Vocal Lead**.
   * Individual track locks (🔒 / 🔓) allow keeping a favored bassline while regenerating new chords, drums, or vocal leads.

5. **In-Browser Web Audio DSP Looper & Synchronized Voice:**
   * Zero-dependency client-side physical voice modeling: Karplus-Strong string plucking, resonator guitars, waveguide wind models, and formant-filtered vocal fold synthesis (700Hz, 1350Hz, 2600Hz formant filters).
   * **Synchronized Lyrics Narration:** Integrates the browser's native Web Speech API to speak/chant the lyric lines in exact synchronization with each chord change as the looper plays.
   * Musician practice suite: Hardware-style LED kill switches (Mute Low / Mid / High / Vocal), 4-beat pre-roll count-in, and auto-ramping **Speed Trainer** (+3 BPM per loop).

6. **Automated Melodic Originality & Copyright Guardrails:**
   * Evaluates generated melodic contours against reference corpora using pitch-interval n-gram similarity.
   * Categorizes outputs as `clean`, `unassessed`, or `possible_match` (which automatically blocks vocal synthesis).

7. **Symbolic Stems & Headless Video Muxing:**
   * Exports multi-track MIDI stems, JSON chord charts, MusicXML, WAV audio mixdown, and a verifiable provenance certificate (`license_cert.json`).
   * Headless video audio replacement (`attach_riff_to_video` via FFmpeg `-c:v copy -an`) with 50MB limits, format whitelisting, and strict shell injection sanitization.

---

## 🚫 What's Explicitly Out of Scope

To keep the agent's blast radius tightly contained and aligned with our musician-first charter, the following are **strictly out of scope**:

1. **Full-Length Song Generation:** The agent refuses prompts requesting complete, radio-ready 3-minute songs (`LOOP_LENGTH_LIMIT`). RIFFs is a practice partner and sketching looper (4-to-8 bar loops), not an automated song-replacement factory.
2. **Direct Commercial Song / Artist Clones:** Refuses verbatim reproductions of copyrighted songs, commercial master recordings, or prompts asking to sound identically like named artists.
3. **Black-Box Flattened Audio Generation:** RIFFs will never generate an opaque audio waveform without an underlying, exportable symbolic score (MIDI/Nashville/Tab).
4. **Server-Side Neural Audio Diffusion Models:** We do not host multi-gigabyte GPU diffusion models on serverless infrastructure. Audio rendering is deterministic, instantaneous, and computed in-browser.
5. **Non-Linear Video Editing (NLE):** There is no video editing UI, timeline, filters, or visual transitions. Video interaction is restricted entirely to headless stream copy audio muxing.
6. **Destructive Cloud Operations:** The agent possesses zero bucket deletion privileges (`storage:delete` revoked) and enforces strict per-session path confinement.

---

## 🔍 Peer Testing Findings & Incorporations

During peer review and security audits, our testing partner surfaced several critical gaps. Here is what was flagged and how each was resolved:

| # | Peer Testing Finding / Gap | Root Cause | Fix Implemented & Verified |
| :-: | :--- | :--- | :--- |
| **1** | **Unbounded Lyrics Prompts Bypassing Safety** | Lyrics prompt could be abused to request full songs or bypass instrumental default boundaries. | Added dual-prompt validation in `validate_prompt()`. Rejects `complete song` / `full song` (`LOOP_LENGTH_LIMIT`) and restricts lyrics generation strictly to a 4-line verse aligned to chord bars. |
| **2** | **Vocal Approval Token Replay & Forgery** | An issued vocal token could theoretically be reused across takes or with modified lyrics. | Implemented HMAC token payloads binding SHA-256 hashes of context and exact lyrics. Enforced atomic once-only consumption with replay protection and fail-closed validation. |
| **3** | **Session Path Scoping & Traversal Vulnerability** | Storage tool paths matched prefixes loosely (e.g. `audio/sessions/abc` matching `audio/sessions/abc_other/...`) and lacked directory traversal checks. | Built `validate_session_storage_path()` enforcing exact trailing slashes (`audio/sessions/{session_id}/`) and blocking `..` path traversal attempts. |
| **4** | **Serverless Production Authentication Failures** | Deployed Vercel site returned HTTP 401 *"Valid bearer token required"* and HTTP 503 *"Vocal signing secret is not configured"*. | Built full JWT UI client with `/api/auth/token` endpoint, fallback signing secrets (`DEFAULT_JWT_SECRET`, `DEFAULT_VOCAL_SECRET`), in-memory rate limiting, and `/tmp` filesystem fallback. |
| **5** | **Vocal Lead Playback Disconnection** | Approved vocal tracks were synthesized in MIDI and WAV export, but silent in live browser playback. | Wired `loop.tiers.vocal` into `tierGainNodes.vocal` in Web Audio mixer, added vocal mute toggle, and added real-time synchronized Web Speech API narration. |

### ⚠️ Known Limitations & Architectural Tradeoffs

Being transparent about architectural boundaries is critical for production readiness:

1. **Serverless Distributed Replay Protection vs. Zero-Config Demo Mode (`token_store.py`):**
   * **The Tradeoff:** True zero-trust replay prevention across distributed serverless workers requires a centralized, atomic data store like Upstash Redis (`KV_REST_API_URL` and `KV_REST_API_TOKEN`). When deployed to serverless environments without external KV credentials provisioned, the backend falls back to an in-memory token store (`_memory_store`) so public demo links function seamlessly without 503 configuration crashes.
   * **The Gap:** In this unconfigured fallback mode, the in-memory store is thread-safe within a single Lambda container, but concurrent requests hitting separate cold containers could theoretically allow a token replay before instance teardown.
   * **Production Recommendation:** For enterprise production deployments, set `RIFFS_REQUIRE_KV=true` to enforce strict fail-closed behavior (`TokenStoreUnavailable`), requiring verified external distributed state before processing vocal authorizations.

2. **Client-Side Web Speech API Synchronization vs. Web Audio Synthesis:**
   * **The Tradeoff:** We chose zero-dependency, browser-native client-side speech synthesis rather than round-tripping to cloud TTS APIs (keeping latency near-zero and free of third-party API costs).
   * **The Gap:** Browser speech engines vary across platforms; Safari iOS and background tabs can throttle or drop `speechSynthesis.speak()` calls if not initiated inside a direct user gesture.
   * **The Fallback:** The musical backing track and synthetic vocal lead (`tierGainNodes.vocal`) run directly inside the low-level Web Audio graph, ensuring uninterrupted playback even if the browser voice narrator stalls.

---

## 🛠️ How to Run It

> [!NOTE]
> **Zero API Keys Required for Full Operation:** The agent runs 100% out-of-the-box using its deterministic music theory, chord parsing, tab generation, and Web Audio DSP engine. Providing an `ANTHROPIC_API_KEY` is completely optional and only used for natural language style enrichment.
> 
> **Zero Build Steps:** There are no Node.js or `npm` build requirements. The frontend is vanilla HTML/CSS/Web Audio served directly by FastAPI.

### Option A: Live Web Application (Instant)
Access the live production deployment directly in any modern desktop or mobile browser:  
👉 **[https://riffs-agent.vercel.app](https://riffs-agent.vercel.app)**

### Option B: Local Web Server
1. **Clone the repository:**
   ```bash
   git clone https://github.com/abheeshudhungana-source/riffs-agent.git
   cd riffs-agent
   ```
2. **Create a virtual environment and install dependencies (Python 3.9+):**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. **Configure environment variables (optional):**
   ```bash
   cp .env.example .env
   # ANTHROPIC_API_KEY is OPTIONAL. If omitted, the agent uses its built-in rule heuristics.
   ```
4. **Start the FastAPI server:**
   ```bash
   uvicorn app:app --reload --port 8000
   ```
   Open `http://localhost:8000` in your browser.

### Option C: Interactive CLI Session Runner
Run the autonomous loop harness directly from your terminal:
```bash
python riff_session.py
```
*(Optional: Install `ffmpeg` via Homebrew or apt if you plan to use headless video audio replacement tools).*

---

### ⚡ 2-Minute Quickstart Test Drive

Follow these 4 steps to test the full agent loop, safety guardrails, and music theory engine:

1. **Step 1: Seed the Instrumental Band & Lyrics Prompts**
   * **Prompt 1 (Instrumental):** Enter `Am - F - C - G`, set tempo to `110 BPM`, and genre style: `"Neo-soul pocket with driving bass"`.
   * **Prompt 2 (Lyrics & Voice):** Enter Theme: `"Midnight highway rain"`, Vocal Style: `Soulful Lead`, Language: `English`.
   * Click **Generate Riff Take**.

2. **Step 2: Test the Human-in-the-Loop (HITL) Vocal Checkpoint**
   * Notice that the agent pauses before synthesizing vocal audio and presents an **"Awaiting Vocal Approval"** modal containing an expiring cryptographic HMAC token.
   * Edit Line 2 directly in the modal (e.g. adjust the rhyme or wording) and click **Approve Vocal Take**.
   * Observe the verified token convert into an active vocal lead track with synchronized Web Speech narration.

3. **Step 3: Test Non-Destructive Track Locking & Practice Suite**
   * In the track mixer deck, click the 🔒 lock button on the **Bass** track.
   * Click **Re-roll Take**—the chords, tabs, drums, and lyrics regenerate while your locked bassline remains completely untouched.
   * Toggle the **Speed Trainer** (+3 BPM per loop) or hardware LED Mute switches to test real-time DSP practice controls.

4. **Step 4: Test Safety & Originality Guardrails**
   * Enter: `"Write me a complete 3-minute radio pop song like Ed Sheeran"`.
   * Verify the agent cleanly rejects the prompt with a helpful explanation referencing `LOOP_LENGTH_LIMIT` (sketching loopers only) and anti-cloning copyright policies.

---

## 🧪 Test Suite & Verification

The codebase includes comprehensive unit, integration, DSP, and security regression coverage:

* **Run Full Backend & Security Test Suite (114 tests):**
  ```bash
  python -m unittest discover tests
  ```
* **Run Headless Audio DSP Synthesis Engine Tests (9 tests):**
  ```bash
  python test_engine.py
  ```

---

## 📂 Project Structure

```
riffs_agent/
├── agent.py                     # Autonomous agent loop, HITL checkpoint, score generator
├── app.py                       # FastAPI API router, JWT auth gateway, and Vercel serverless entrypoint
├── composer.py                  # Symbolic music composition engine (Nashville, Tabs, Chords)
├── riff_session.py              # Interactive CLI session harness with soft-delete trash
├── test_engine.py               # Headless JavaScriptCore audio DSP verification suite
├── index.html                   # Interactive frontend, Web Audio synthesizer, and practice UI
├── requirements.txt             # Python runtime dependencies
├── riffs_api/
│   ├── agent_loop.py            # Sandboxed agent loop environment & tool runner
│   ├── audit_trace.py           # Structured, redacted operational audit logging
│   ├── originality.py           # Melodic similarity contour comparison
│   ├── progression.py           # Chord progression & scale degree parser
│   ├── prompt_guardrails.py     # Anti-plagiarism, instrumental-only, and loop limit checks
│   ├── prompt_intent.py         # Natural language prompt extraction
│   ├── render.py                # Symbolic package renderer (MusicXML, MIDI, JSON)
│   ├── storage.py               # Session-scoped storage tools with path validation
│   ├── take_store.py            # Local & serverless persistent take archive
│   ├── token_store.py           # Atomic single-use token store for vocal approval
│   ├── video.py                 # Headless FFmpeg video remuxing with shell sanitization
│   └── vocal_approval.py        # Cryptographic HMAC token signing & verification
├── tests/                       # 114 automated test cases
└── docs/                        # Complete PRDs, architecture diagrams, and threat models
```
