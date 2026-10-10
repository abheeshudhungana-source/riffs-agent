# RIFFs: AI Practice & Sketching Partner for Musicians

**Owners:** Abheeshu Dhungana & Michael Goslin  
**Version:** 0.1.0 (MVP)  
**Status:** In Active Development  

> **One-Line Purpose:**  
> RIFFs is an AI practice and sketching partner for musicians. The current build focuses on chord-first charts and symbolic MIDI; audio rendering is still future work.

---

## 🎯 What RIFFs Does
Unlike audio-first jukeboxes that generate audio and guess the notes afterward, **RIFFs writes the notes first (the recipe before the cake)**:
- **Input Your Own Ideas:** Seed the band with typed chords (`Am - F - C - G` or Nashville Numbers `1 - 4 - 5 - 1`) or genre prompts.
- **Working Musician Charts:** Nashville Number charts and a basic chord-shape guitar tab preview.
- **Part-Locking & Takes:** Lock a selected symbolic MIDI lane across takes in the current server process. The score engine is an initial block-chord baseline.
- **Practice Suite:** Hardware-style LED kill switches (Mute Low / Mid / High, Metronome with green LED), Register tier instrument assignments (Low, Mid, High), Speed Trainer (+3 BPM auto-ramp per loop), and count-in pre-roll.
- **Symbolic Export:** MIDI, MusicXML, and chord chart JSON. The frontend's Save MP3 control and video dubbing navigation are prototypes; they do not produce audio or video yet.

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

For backend setup, request examples, Day 1 scope, and known limitations, see [docs/BACKEND.md](docs/BACKEND.md) and [docs/BACKEND_PRD_MAP.md](docs/BACKEND_PRD_MAP.md).
