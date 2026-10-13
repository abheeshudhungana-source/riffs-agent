# RIFFs: Monday Design Pitch Outline & Verbatim Script
## Focus: Design Rationale & Architecture (Not a Product Demo)

- **Total Target Time:** 3 Minutes 30 Seconds (Strictly under the 4:00 hard cap)
- **Speakers:** Abheeshu Dhungana & Michael Goslin
- **Visuals to Show on Screen:** 
  1. Slide 1: Industry Choice & Problem Space
  2. Slide 2: PRD Highlights & Target Personas (70% Creators / 30% Musicians)
  3. Slide 3: The System Prompt & Guardrails
  4. Slide 4: System Architecture Diagram & Tool Sinks
  5. Slide 5: Why This Design Will Work (The Defensibility Moat)

---

## ⏱️ Section-by-Section Timing & Speaker Allocation

```
[0:00 - 0:35] Part 1: Industry, Functional Area & Why (Abheeshu) - 35s
[0:35 - 1:10] Part 2: Role of the Agent & PRD Scope (Abheeshu) - 35s
[1:10 - 1:45] Part 3: System Prompt Deep-Dive (Abheeshu) - 35s
[1:45 - 2:25] Part 4: System Architecture & Tool Sinks (Michael) - 40s
[2:25 - 3:05] Part 5: Why This Design Will Work (Michael) - 40s
[3:05 - 3:30] Part 6: Summary & Hand-off (Michael & Abheeshu) - 25s
─────────────────────────────────────────────────────────────
TOTAL DURATION: 3 Minutes 30 Seconds (Safe buffer under 4:00)
```

---

## 🎙️ Verbatim Speaking Script

### PART 1: Industry, Functional Area & Why (0:00 - 0:35)
**Speaker: Abheeshu Dhungana**  
**Visual on Screen:** *Slide 1 — Music Tech / Creator Economy Landscape*

> "Good morning everyone. Michael and I designed **RIFFs**, an autonomous harmonic co-producer situated at the intersection of **Music Tech and the Creator Economy**.
>
> We deliberately chose this space because 70% of short-form video creators on TikTok and Reels face immediate demonetization from commercial copyright strikes, while instrumentalists lose creative momentum in disorganized voice memos. 
> 
> Current generative audio tools like Suno operate as black boxes—they generate audio first and guess the notes backward, producing un-editable tracks with audio artifacts. We identified an urgent need for an AI agent that operates like a session musician: drafting musical notes before rendering sound."

---

### PART 2: Role of the Agent & PRD Scope (0:35 - 1:10)
**Speaker: Abheeshu Dhungana**  
**Visual on Screen:** *Slide 2 — PRD Summary & Target Personas*

> "The role of RIFFs is not to replace the human artist, but to serve as an **autonomous rehearsal partner and arrangement co-pilot**. 
>
> In our PRD, we prioritized two core personas: **70% short-form creators** who need custom, royalty-safe background riffs dubbed onto raw phone footage in under 1.5 seconds, and **30% working musicians and learners** who need Nashville chord charts, guitar tabs, and tempo trainers.
>
> To keep the agent’s blast radius contained, our PRD sets three non-negotiable boundaries: strictly instrumental riffs—no vocal synthesis, an anti-plagiarism melodic contour guardrail that refuses commercial copies, and headless video muxing with zero video editor UI."

---

### PART 3: The System Prompt (1:10 - 1:45)
**Speaker: Abheeshu Dhungana**  
**Visual on Screen:** *Slide 3 — The System Prompt & Behavioral Schema*

> "To enforce these boundaries, our agent harness is governed by this system prompt:
> 
> *'You are RIFFs, an autonomous music theory and acoustic sketching co-producer. You write the notes first—the recipe before the cake—then render them into realistic acoustic multisamples. You ingest typed chords or Nashville numbers, enforce locked parts, and output strict diatonic JSON blueprints.'*
> 
> The prompt forces the LLM to think in symbolic pitch classes, octave registers, and metric subdivisions rather than raw audio tokens. It explicitly instructs the model to preserve locked parts byte-for-byte across iterations, preventing the model from re-rolling tracks the musician already loves."

---

### PART 4: Architecture Diagram & Tool Sinks (1:45 - 2:25)
**Speaker: Michael Goslin**  
**Visual on Screen:** *Slide 4 — 5-Stage Architecture Flowchart*

> "Thank you, Abheeshu. I’ll walk you through our system architecture. 
>
> Our pipeline flows through five distinct stages:
> 1. **Ingress:** Accepts typed chord progressions like `Am - F - C - G` or Nashville numbers `1 - 4 - 5 - 1`, validated on the client before submission.
> 2. **Agent Harness:** The loop tracks up to 5 iterative takes, manages session state, and passes locked lane vectors to the LLM.
> 3. **Symbolic Score & Licensing Gate:** Computes exact Nashville degrees, 6-string guitar tabs, and hashes a cryptographic Royalty-Free License Certificate.
> 4. **Tool 1 (`render_riff_to_audio`):** Synthesizes isolated multisampled WAV stems and 320kbps master MP3s with standardized DAW naming.
> 5. **Tool 2 (`attach_riff_to_video`):** A headless FFmpeg utility that strips mic noise and stream-copies the riff into MP4 video in under 1.5 seconds without re-encoding frames."

---

### PART 5: Why This Design Will Work (2:25 - 3:05)
**Speaker: Michael Goslin**  
**Visual on Screen:** *Slide 5 — Defensibility, Resilience & Viability*

> "We believe this design will succeed in production for three core reasons:
>
> First, **Architectural Defensibility**: By adopting 'the recipe before the cake' approach, our chord charts, tabs, and stems are exact ground-truth mathematical reality, completely eliminating generative audio hallucinations.
>
> Second, **Dual-Layer Resilience**: Even if the cloud LLM experiences network latency or API rate limits, our agent harness is paired with a deterministic local music theory engine that guarantees 0% runtime crash rates.
>
> Third, **Market Viability**: For creators, the verifiable license certificate solves copyright anxiety at the root. For musicians, the hardware-style part-locking and practice suite turn static sketches into active practice partners."

---

### PART 6: Conclusion (3:05 - 3:30)
**Speaker: Michael Goslin & Abheeshu Dhungana**  
**Visual on Screen:** *Slide 5 — Closing Slide / Q&A*

> **Michael:** "In summary, RIFFs bridges the gap between chaotic phone voice memos and black-box generative AI by putting symbolic structure first."
>
> **Abheeshu:** "It delivers immediate copyright-safe audio for creators and exact musical control for instrumentalists. Thank you, and we're ready for your questions."

---

## 📋 Evaluation Checklist Verification

| Rubric Requirement | How It Is Addressed in Script | Time Allocation |
| :--- | :--- | :---: |
| **Industry & Functional Area + Why** | Music Tech & Creator Economy; solving creator copyright strikes & voice memo graveyard | 0:00 - 0:35 (35s) |
| **Role of the Agent** | Autonomous harmonic co-producer and practice co-pilot | 0:35 - 1:10 (35s) |
| **PRD Scope & Guardrails** | 70% creators / 30% musicians; strictly instrumental, anti-plagiarism, headless mux | 0:35 - 1:10 (35s) |
| **System Prompt** | Direct quote of system prompt; symbolic note vectors and locked track enforcement | 1:10 - 1:45 (35s) |
| **Architecture Diagram** | 5-stage pipeline: Ingress &rarr; Harness &rarr; Symbolic Gate &rarr; `render_riff_to_audio` &rarr; `attach_riff_to_video` | 1:45 - 2:25 (40s) |
| **Why Design Will Work** | Notes-first truth, dual-layer deterministic resilience, provable licensing clearance | 2:25 - 3:05 (40s) |
| **Hard Cap Compliance** | Total presentation script runs in **3 minutes 30 seconds** (leaves 30s buffer under 4:00) | **3:30 Total** |
