# RIFFs: AI Practice & Sketching Partner for Musicians

**Owners:** Abheeshu Dhungana & Michael Goslin  
**Version:** 0.1.0 (MVP)  
**Status:** In Active Development  

> **One-Line Purpose:**  
> An autonomous AI practice and sketching partner for musicians that writes notes before audio, generates exact chord charts and guitar tabs, and accompanies players with realistic acoustic multisamples.

---

## 🎯 What RIFFs Does
Unlike audio-first jukeboxes that generate audio and guess the notes afterward, **RIFFs writes the notes first (the recipe before the cake)**:
- **Input Your Own Ideas:** Seed the band with typed chords (`Am - F - C - G` or Nashville Numbers `1 - 4 - 5 - 1`) or genre prompts.
- **Working Musician Charts:** Triple-view of Nashville Number Chord Charts, 6-String Guitar Tablature, and traditional Staff Notation.
- **Part-Locking & Takes:** Lock parts you love (e.g. lock the bassline 🔒) and regenerate only the drums or lead, with full version history.
- **Practice Suite:** Hardware-style LED kill switches (Mute Low / Mid / High, Metronome with green LED), Register tier instrument assignments (Low, Mid, High), Speed Trainer (+3 BPM auto-ramp per loop), and count-in pre-roll.
- **Audio & Social Export:** 1-click high-fidelity MP3 export (`Save MP3` at 320kbps) for instant practice capture; decoupled video dubbing placeholder (`attach_riff_to_video`).

---

## 📁 Project Architecture & Layout

```
riffs_agent/
├── .env                  # Secret credentials (ANTHROPIC_API_KEY) - [GITIGNORED]
├── .env.example          # Safe template for collaborator credentials
├── .gitignore            # Strict protection against leaking keys and audio binaries
├── README.md             # Project overview and daily setup guide
├── requirements.txt      # Core Python dependencies (litellm, python-dotenv, etc.)
├── agent.py              # Main autonomous agent harness & loop
├── app.py                # FastAPI backend & Vercel serverless entrypoint
├── test_model.py         # Verification script to test Claude connectivity
├── index.html            # Production interactive frontend & practice dashboard
├── config/
│   ├── llm_config.json   # Model registry (Claude Sonnet 5.5, Gemini, GPT)
│   └── render_endpoint_map.json # Audio rendering endpoint registry
└── docs/
    ├── PRD.md            # Complete Product Requirements Document & Eval Cards
    └── CLAUDE_DESIGN_PROMPT.md # Day 2 Zero-Token-Waste Claude Prompt Specification
```

---

## 🚀 Quickstart for Collaborators (Abheeshu & Michael)

### 1. Clone & Set Up Environment
```bash
git clone <repo-url>
cd riffs_agent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Your API Key
Copy the template and paste your Anthropic API key:
```bash
cp .env.example .env
# Edit .env and set: ANTHROPIC_API_KEY=your_key_here
```

### 3. Verify the AI Agent Harness
Run the verification test script:
```bash
python test_model.py
```
If configured correctly, Claude will return a live confirmation greeting.

---

## 📜 Complete Documentation
For full technical specifications, user personas, threat models, and eval cards, read the [PRD](docs/PRD.md).
