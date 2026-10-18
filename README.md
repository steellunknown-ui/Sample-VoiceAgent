<div align="center">

# 🎙️ Aria AI — Multilingual Voice Console
### Enterprise-Grade Conversational Voice Agent with Specialized Model Routing

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0.3-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![ElevenLabs](https://img.shields.io/badge/ElevenLabs-TTS-FF6B6B?style=for-the-badge&logo=soundcharts&logoColor=white)](https://elevenlabs.io/)
[![Sarvam AI](https://img.shields.io/badge/Sarvam.ai-Indic_TTS-FFA500?style=for-the-badge)](https://sarvam.ai/)
[![faster-whisper](https://img.shields.io/badge/faster--whisper-int8-brightgreen?style=for-the-badge)](https://github.com/SYSTRAN/faster-whisper)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)](LICENSE)

<br />

<p align="center">
  <strong>A real-time multilingual voice assistant pairing local quantized STT, specialized neural speech synthesis, and an executive dark-mode console.</strong>
  <br />
  Featuring strict language-to-engine binding, zero-downtime fallback recovery, and browser-side Voice Activity Detection (VAD).
</p>

[Key Features](#-key-features) •
[Architecture](#-system-architecture) •
[Engineering Highlights](#-engineering-highlights-for-recruiters) •
[Quick Start](#-quick-start) •
[API Reference](#-api-specification) •
[Architecture Deep-Dive](ARCHITECTURE.md)

</div>

---

## 💡 Overview

Building production-ready voice agents requires addressing three core engineering bottlenecks:
1. **The Regional Phonetics Deficit:** Generic global TTS models mispronounce regional dialects and mixed codes (e.g., Hinglish, Marathi).
2. **Third-Party API Fragility:** Strict rate limits and credit boundaries cause hard stops in conversation flow.
3. **Latency Accumulation:** Combining cloud transcription, LLM reasoning, and audio streaming can cause awkward multi-second silences.

**Aria AI** solves these challenges using a **hybrid edge-and-cloud architecture**:
- **Local int8 Speech Recognition** via `faster-whisper` for low-latency transcription without per-minute cloud bills.
- **Strict Speech Engine Dispatching:** English routes to **ElevenLabs** for hyper-realistic human emotion, while Hinglish and Marathi route to **Sarvam.ai (`bulbul:v3`)** for authentic Indian phonetics.
- **Zero-Downtime Circuit Breaker:** Instant automatic failover to **Microsoft Edge Neural TTS** if upstream third-party quotas are reached.
- **In-Browser VAD:** Audio energy analysis triggers autonomous turn-taking without needing ongoing WebSocket streaming.

---

## ✨ Key Features

- 🇬🇧 **English via ElevenLabs:** Studio-grade conversational warmth with the **George** voice (`JBFqnCBsd6RMkjVDRZzb`).
- 🇮🇳 **Hinglish & Marathi via Sarvam.ai:** Native Indic acoustic model (`bulbul:v3`) with the **Ashutosh** deep male voice.
- 🛡️ **Zero-Downtime Fallback Mesh:** Uninterrupted service via Microsoft Edge Neural voices if upstream APIs return `401`, `402`, or `429`.
- ⚡ **Hands-Free Live Mode:** Browser-level VAD tracks microphone audio energy and submits turns upon detecting a ~1.0s silence window.
- 🔘 **Push-to-Talk Mode:** Manual mic trigger for structured query submission in noisy environments.
- 🧠 **Context-Preserving LLM:** OpenRouter orchestrator with conversation memory, prompt-injected guardrails, and rapid conversational failovers.
- 🎨 **Executive Dark Navy Console:** Bespoke glassmorphism interface with dynamic audio spectrum visualizer and state-reactive glowing ambient orb.

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    BROWSER CLIENT (UI)                      │
│  • Web Audio API Analyser     • Hands-Free VAD Loop         │
│  • Dynamic Frequency Visualizer • Live State Ambient Orb    │
└──────────────────────────────┬──────────────────────────────┘
                               │ Multipart Audio / JSON
                               ▼
┌─────────────────────────────────────────────────────────────┐
│               FLASK REST GATEWAY (Python 3.11)              │
│  • Request routing & session isolation                     │
│  • Speech language constraint enforcement                   │
└──────────────┬───────────────────────────────┬──────────────┘
               │                               │
               ▼                               ▼
┌──────────────────────────────┐ ┌────────────────────────────┐
│   LOCAL STT ENGINE (int8)    │ │   LLM CONVERSATION MGR     │
│   • faster-whisper (CPU)     │ │   • OpenRouter Gateway     │
│   • CTranslate2 inference    │ │   • Sliding-window memory  │
│   • Zero hallucination lock  │ │   • Moderation guardrails  │
└──────────────────────────────┘ └─────────────┬──────────────┘
                                               │ Clean Text
                                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 SMART TTS DISPATCH MATRIX                   │
│                                                             │
│   Language == 'en'         ──►  ElevenLabs API (George)    │
│   Language == 'hi' / 'mr'  ──►  Sarvam.ai API (Ashutosh)   │
│   On Quota/Rate Limit (429)──►  Edge-TTS Safety Mesh (Free) │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 Engineering Highlights (For Recruiters & Evaluators)

| Capability | Implementation | Value / Impact |
| :--- | :--- | :--- |
| **Speech-to-Text Latency** | `faster-whisper` quantized to `int8` running on CPU workers | Sub-400ms transcription with zero API dependency or transcription cost. |
| **Anti-Hallucination Guard** | STT pipeline accepts explicit `target_language` bounds (`en`, `hi`, `mr`) | Completely eliminates Whisper's tendency to hallucinate foreign IDs (e.g., `id`) during ambient silence. |
| **Linguistic Authenticity** | Specialized API partitioning (ElevenLabs for EN, Sarvam for Indic) | Prevents the robotic foreign accent common in one-size-fits-all multilingual TTS engines. |
| **Fault Tolerance & Reliability** | Built-in circuit breaker fallback to Microsoft Edge-TTS | System never crashes or goes silent when third-party credits run out. |
| **Token Economy & Velocity** | `max_tokens=120`, suppressed reasoning effort, clean string truncation | Preserves finite user API credits while ensuring snappy, natural voice turnarounds. |
| **Secret Hygiene & Security** | Strict `.gitignore` rules + comprehensive `.env.example` template | Zero API keys, private tokens, or credentials committed to source control. |

---

## 📁 Repository Structure

```
Sample-Voiceagent/
├── app.py                    # Flask HTTP gateway & audio turn endpoints
├── requirements.txt          # Production Python dependencies
├── .env.example              # Sanitized configuration template
├── .gitignore                # Multi-layer secret & cache exclusion
├── README.md                 # Project overview & documentation
├── ARCHITECTURE.md           # Engineering deep-dive & sequence specifications
├── setup.ps1                 # Automated Windows PowerShell bootstrapper
├── modules/
│   ├── stt.py                # Speech-to-Text inference (faster-whisper int8)
│   ├── llm.py                # Multi-turn LLM pipeline & content guardrails
│   ├── tts.py                # Multi-provider voice dispatcher & fallback mesh
│   └── conversation.py       # Session memory manager with sliding window
└── static/
    ├── index.html            # Executive voice workstation console
    ├── style.css             # Dark cobalt glassmorphism design system
    └── app.js                # VAD audio engine & frontend controller
```

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10+
- Modern Web Browser (Chrome, Edge, Firefox, Safari)

### 2. Installation

```bash
# Clone the repository
git clone https://github.com/steellunknown-ui/Sample-VoiceAgent.git
cd Sample-VoiceAgent

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Setup

Copy the configuration template:
```bash
cp .env.example .env
```

Populate your `.env` with your API keys:
```dotenv
# Required for conversational intelligence
OPENROUTER_API_KEY=your_openrouter_api_key_here

# For English Voice Synthesis (ElevenLabs)
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
ELEVENLABS_VOICE_ID=JBFqnCBsd6RMkjVDRZzb

# For Hinglish & Marathi Voice Synthesis (Sarvam.ai)
SARVAM_API_KEY=your_sarvam_api_key_here
SARVAM_SPEAKER=ashutosh
```

### 4. Launch Application

```bash
python app.py
```

Access the console at:
```
http://localhost:5000
```

---

## 📡 API Specification

### 1. Voice Turn (`POST /api/chat/voice`)
Submits audio from the browser microphone for transcription, LLM processing, and voice synthesis.

- **Request:** `multipart/form-data`
  - `audio`: Binary audio file (`audio/wav`, `audio/webm`)
  - `language`: `en` | `hi` | `mr`
  - `session_id`: String identifier
- **Response:** `application/json` (HTTP 200)
  ```json
  {
    "transcription": "What can you help me with?",
    "response_text": "I can assist you with technical troubleshooting, daily planning, or general questions. What are we working on?",
    "audio_base64": "UklGRi...",
    "language": "en",
    "provider": "ElevenLabs (George)",
    "session_id": "default",
    "turn": 1
  }
  ```

### 2. Text Turn (`POST /api/chat/text`)
Direct text invocation for automated testing and keyboard input.

- **Request:** `application/json`
  ```json
  {
    "message": "Hello Aria",
    "language": "en",
    "session_id": "default"
  }
  ```

### 3. Health & Readiness (`GET /api/health`)
Returns service telemetry, loaded Whisper model size, and fallback status.

---

## 🛡️ License

This project is licensed under the [MIT License](LICENSE).
Feel free to use, modify, and distribute for personal or commercial projects.
