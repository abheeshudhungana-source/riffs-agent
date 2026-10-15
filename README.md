# RIFFs: Autonomous Music Theory & Acoustic Sketching Co-Producer

[![CI / Regression Tests](https://img.shields.io/badge/tests-verification%20pending-yellow)](https://github.com/abheeshudhungana-source/riffs-agent)
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

To prevent architectural scope creep and protect musicians' creative ownership, the following are **deliberately and explicitly out of scope** (and should not be mistaken for missing features):

1. **Full-Length (3+ Minute) Radio Song Generation:**
   * **Why it's out of scope:** RIFFs is engineered as an interactive practice partner and co-producer for rehearsal and sketching (4-to-8 bar loops), not an automated song-replacement factory.
   * **Enforced Behavior:** The agent actively enforces `LOOP_LENGTH_LIMIT` in prompt validation and safely refuses prompts requesting "full songs", "entire tracks", or "complete 3-minute arrangements".
   * **Musician Alternative:** Musicians export multi-track MIDI stems and MusicXML into their DAW (Logic, Ableton, Pro Tools) to assemble full song structures around their favorite riff takes.

2. **Hyper-Realistic Neural Voice / Artist Cloning:**
   * **Why it's out of scope:** We deliberately avoid proprietary cloud voice-cloning APIs (e.g. ElevenLabs, Suno audio diffusion) to eliminate deepfake voice identity theft, copyright liability, and heavy API latency.
   * **Enforced Behavior:** Vocal synthesis is performed entirely client-side using deterministic formant filtering (700Hz, 1350Hz, 2600Hz vocal fold acoustics) and browser-native Web Speech API synchronization.

3. **Direct Commercial Song / Artist Plagiarism:**
   * **Why it's out of scope:** Ethical and legal boundaries require that our agent does not reproduce copyrighted commercial melodies or master recordings.
   * **Enforced Behavior:** Prompts requesting exact clones of named copyrighted tracks trigger anti-plagiarism guardrail refusals, and melodic contours are evaluated via `originality.py` pitch-interval n-gram similarity.

4. **Digital Audio Workstation (DAW) Recording / Live Mic Tracking:**
   * **Why it's out of scope:** RIFFs is a symbolic co-producer and notation generator, not a multi-track recording studio or native C++ audio plugin (VST3/AU/AAX).
   * **Musician Alternative:** Use the browser Web Audio looper for immediate rehearsal; record real instruments against exported WAV mixes or import the MIDI into a DAW.

5. **Black-Box Flattened Audio Generation:**
   * **Why it's out of scope:** Generating an opaque, non-editable audio waveform without inspectable chords, tabs, and Nashville numbers defeats the purpose of music theory education and human practice.
   * **Enforced Behavior:** Every sound heard in the looper is derived strictly from an underlying, inspectable, and editable symbolic score (`score_data`).

6. **Non-Linear Video Editing (NLE) & Visual FX:**
   * **Why it's out of scope:** Video tooling is restricted strictly to headless stream copy audio muxing (`attach_riff_to_video` via FFmpeg `-c:v copy -an`). There are no timelines, color grading, visual filters, or transition effects.

7. **Destructive Cloud Operations & Unbounded Storage:**
   * **Why it's out of scope:** The current agent does not need general-purpose storage tools. Its tool allowlist contains only progression parsing, score drafting, and symbolic export; take API reads check the authenticated owner.

---

## 🔍 Peer Testing Findings & Incorporations

During peer review and security audits, our testing partner surfaced several critical gaps. Here is what was flagged and how each was resolved:

| # | Peer Testing Finding / Gap | Root Cause | Fix Implemented & Verified |
| :-: | :--- | :--- | :--- |
| **1** | **Unbounded Lyrics Prompts Bypassing Safety** | Lyrics prompt could be abused to request full songs or bypass instrumental default boundaries. | Added dual-prompt validation in `validate_prompt()`. Rejects `complete song` / `full song` (`LOOP_LENGTH_LIMIT`) and restricts lyrics generation strictly to a 4-line verse aligned to chord bars. |
| **2** | **Vocal Approval Token Replay & Forgery** | An issued vocal token could theoretically be reused across takes or with modified lyrics. | Implemented HMAC token payloads binding SHA-256 hashes of context and exact lyrics. Enforced atomic once-only consumption with replay protection and fail-closed validation. |
| **3** | **Session Ownership & Unneeded Tool Access** | Take reads did not check record ownership, and the allowlist included unused storage, publishing, invite, and remux stubs guarded only by a caller-controlled `approved` flag. | Take records now carry the authenticated subject; API reads and take reuse are owner-scoped. The agent allowlist contains only progression parsing, score drafting, and symbolic export. The video-remux route requires the generation entitlement. |
| **4** | **Serverless Production Authentication Failures** | Static fallback signing secrets and an unauthenticated token-mint endpoint could grant anyone a beta generation token; in-memory rate limits were not shared across instances. | Static JWT and vocal secrets were removed. `/api/auth/token` only issues an ephemeral local demo token when `RIFFS_ENABLE_DEMO_AUTH=true` and is disabled on deployments. Deployed generation fails closed without configured JWT settings and shared Redis rate limits. Vocal approval requires a configured secret and shared replay store. |
| **5** | **Vocal Lead Playback Disconnection** | Approved vocal tracks were synthesized in MIDI and WAV export, but silent in live browser playback. | Wired `loop.tiers.vocal` into `tierGainNodes.vocal` in Web Audio mixer, added vocal mute toggle, and added real-time synchronized Web Speech API narration. |

### ⚠️ Known Limitations & Architectural Tradeoffs

Being transparent about architectural boundaries is critical for production readiness:

1. **Shared Authentication and Replay Storage:**
   * **Local Demo Mode:** Set `RIFFS_ENABLE_DEMO_AUTH=true` in a local `.env` to enable the UI's local token helper. It uses a process-random signing secret and cannot mint tokens in Vercel or AWS Lambda.
   * **Staging and Production:** Configure `RIFFS_JWT_SECRET`, issuer, audience, `REDIS_URL`, `RIFFS_VOCAL_SECRET`, and shared Upstash/Vercel KV credentials. The deployment fails closed when required auth, rate-limit, signing, or replay storage is missing or unavailable. Never use demo auth or local in-memory storage for staging or production validation.
   * **Staging Status:** A real IdP-issued token and live shared Redis/KV connection still need end-to-end validation in staging.

2. **Client-Side Web Speech API Synchronization vs. Web Audio Synthesis:**
   * **The Tradeoff:** We chose zero-dependency, browser-native client-side speech synthesis rather than round-tripping to cloud TTS APIs (keeping latency near-zero and free of third-party API costs).
   * **The Gap:** Browser speech engines vary across platforms; Safari iOS and background tabs can throttle or drop `speechSynthesis.speak()` calls if not initiated inside a direct user gesture.
   * **The Fallback:** The musical backing track and synthetic vocal lead (`tierGainNodes.vocal`) run directly inside the low-level Web Audio graph, ensuring uninterrupted playback even if the browser voice narrator stalls.

---

## 🛠️ How to Run It

> [!NOTE]
> **No model-provider key required for core generation:** Instrumental composition uses deterministic music theory and the Web Audio preview. Local API use opts into the local-only demo token helper via `RIFFS_ENABLE_DEMO_AUTH=true`; vocal approval additionally needs a locally generated `RIFFS_VOCAL_SECRET`. Demo token issuance is disabled on deployments. Staging and production require an IdP-issued token plus shared Redis/KV configuration.
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
3. **Configure local environment variables:**
   ```bash
   cp .env.example .env
   # RIFFS_ENABLE_DEMO_AUTH=true is local-only; deployment code ignores it.
   # For local vocal approval, set RIFFS_VOCAL_SECRET to a fresh random value:
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   # Paste the printed value into .env as RIFFS_VOCAL_SECRET.
   # ANTHROPIC_API_KEY remains optional for core deterministic generation.
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

* **Run Full Backend & Security Test Suite:**
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
│   ├── agent_loop.py            # Deterministic loop using the allowlisted tools
│   ├── audit_trace.py           # Structured, redacted operational audit logging
│   ├── originality.py           # Melodic similarity contour comparison
│   ├── progression.py           # Chord progression & scale degree parser
│   ├── prompt_guardrails.py     # Anti-plagiarism, instrumental-only, and loop limit checks
│   ├── prompt_intent.py         # Natural language prompt extraction
│   ├── render.py                # Symbolic package renderer (MusicXML, MIDI, JSON)
│   ├── storage.py               # Shared Redis client for rate limits and replay storage
│   ├── take_store.py            # Local take archive with authenticated-owner checks
│   ├── tool_access.py           # Least-privilege allowlist for the three active tools
│   ├── token_store.py           # Atomic single-use token store for vocal approval
│   ├── video.py                 # Headless FFmpeg video remuxing with shell sanitization
│   └── vocal_approval.py        # Cryptographic HMAC token signing & verification
├── tests/                       # Backend, security, and regression tests
└── docs/                        # Complete PRDs, architecture diagrams, and threat models
```
