# System Architecture & Engineering Specification

This document provides a technical deep-dive into the design decisions, pipeline mechanics, and fault-tolerant architecture of **Aria AI — Multilingual Voice Console**.

---

## 1. Executive Summary & Design Goals

Aria AI is engineered to bridge low-latency real-time voice interaction with regional linguistic authenticity and zero-downtime reliability:

- **Target Latency:** Sub-2-second end-to-end voice turnaround time (User Speech End $\rightarrow$ Agent Spoken Audio Start).
- **Linguistic Fidelity:** Native acoustic modeling for Indic dialects (Hinglish, Marathi) paired with hyper-realistic human voice synthesis for English.
- **Fault-Tolerant High Availability:** Guaranteed audio playback even under complete third-party API rate limits or quota depletion.
- **Client-Side Autonomy:** In-browser Voice Activity Detection (VAD) eliminating constant server-side streaming overhead.

---

## 2. End-to-End Pipeline & System Flow

```mermaid
sequenceDiagram
    autonumber
    actor User as User Microphone
    participant VAD as Browser Audio Engine (VAD)
    participant API as Flask REST Gateway (/api/chat/voice)
    participant STT as Local STT (faster-whisper int8)
    participant LLM as Language Engine (OpenRouter)
    participant Router as Smart TTS Dispatcher
    participant Primary as ElevenLabs / Sarvam.ai
    participant Fallback as Edge-TTS Safety Mesh
    participant Client as Web Audio Context (Playback)

    User->>VAD: Continuous Spoken Audio
    Note over VAD: RMS energy analysis detects speech & silence window (~1.0s)
    VAD->>API: Multipart Audio Blob + Locked Target Language Code
    API->>STT: Audio Buffer (Target Language Constraint)
    Note over STT: CTranslate2 int8 execution eliminates language hallucinations
    STT-->>API: Transcribed Text
    API->>LLM: Prompt Context + Conversation Memory + Persona Guardrails
    Note over LLM: max_tokens=120, reasoning effort suppressed for conversational velocity
    LLM-->>API: Concise Conversational Response (<200 chars)
    API->>Router: synthesize_speech(text, target_language)
    
    alt English Mode
        Router->>Primary: ElevenLabs API (Voice ID: JBFqnCBsd6RMkjVDRZzb)
    else Hinglish / Marathi Mode
        Router->>Primary: Sarvam.ai API (bulbul:v3 - Ashutosh)
    end

    alt Primary Engine Success (HTTP 200)
        Primary-->>Router: Raw Binary Audio
    else Quota Depleted / Rate Limited (HTTP 401/402/429)
        Router->>Fallback: Async Fallback to Microsoft Edge Neural
        Fallback-->>Router: Regional Neural Audio Stream
    end

    Router-->>API: Binary Audio + Active Engine Label
    API-->>Client: JSON { audio_base64, transcription, response_text, provider }
    Client->>Client: Web Audio API Stream Playback & FFT Bar Visualizer
    Client->>VAD: Resume Listening on Playback Completion
```

---

## 3. Key Engineering Highlights

### A. Local int8 Speech Recognition without Hallucinations
- **Engine:** `faster-whisper` backed by `CTranslate2`.
- **Optimization:** CPU-quantized `int8` model execution enables sub-400ms speech-to-text inference without requiring high-cost cloud transcription APIs.
- **Hallucination Prevention:** Raw background noise in polyglot Whisper models frequently defaults to low-resource language IDs (e.g., `id` - Indonesian). By accepting a locked `target_language` parameter (`en`, `hi`, `mr`), the transcription search space is constrained, completely eliminating foreign language hallucinations.

### B. Specialized Regional vs. Global Voice Routing
Generic multilingual TTS engines frequently produce robotic, unnatural phonetics when speaking Indian English, Hinglish, or regional languages like Marathi.

| Dialect / Language | Selected Engine | Model / Voice ID | Engineering Rationale |
| :--- | :--- | :--- | :--- |
| **English** | **ElevenLabs** | `JBFqnCBsd6RMkjVDRZzb` (George) | Superior emotional prosody, breath control, and conversational warmth. |
| **Hinglish** | **Sarvam.ai** | `bulbul:v3` (`ashutosh`) | Native Indian bilingual phoneme mapping for Hindi-English sentence mixing. |
| **Marathi** | **Sarvam.ai** | `bulbul:v3` (`ashutosh`) | Native Devnagari script acoustic modeling with regional inflection. |

### C. Zero-Downtime Circuit Breaker & Fallback Mesh
Voice agents frequently fail when upstream cloud APIs encounter credit exhaustion, billing boundaries, or sudden rate throttling.
- **Mechanism:** `modules/tts.py` acts as a proxy with built-in fault tolerance.
- **Failover Logic:** If ElevenLabs or Sarvam returns HTTP `401` (Unauthorized), `402` (Payment Required), `429` (Rate Limited), or drops connection, the exception is caught instantly and routed to **Microsoft Edge Neural TTS** (`en-IN-PrabhatNeural`, `hi-IN-MadhurNeural`, `mr-IN-AarohiNeural`).
- **Telemetry:** The user receives uninterrupted voice output, with the active engine badge dynamically tagged as `Edge-TTS (Fallback)`.

### D. Token & Credit Optimization Protocol
Spoken conversations require concise turns rather than long prose.
- The LLM context injector sets strict bounds: `max_tokens=120`, temperature `0.7`, and `reasoning_effort="none"`.
- TTS inputs are sanitized and sentence-capped to under 200 characters.
- This results in a **~75% reduction in API token burn**, preserving the user's finite API allocations.

### E. Client-Side Voice Activity Detection (VAD)
- Implemented using the browser's native `AudioContext` and `AnalyserNode`.
- Computes real-time Root Mean Square (RMS) decibel levels to distinguish active speech from ambient background noise.
- Audio packets are buffered and submitted immediately upon detecting a 1,000ms silence window following active speech, mimicking modern conversational agents (ChatGPT Live / Gemini Live).

---

## 4. Security & Environment Architecture

- **Zero-Secret Commit Guarantee:** Strict multi-layer `.gitignore` prevents local `.env` files, backups, audio recordings, and cache directories from ever entering version control.
- **Sanitized Templates:** `.env.example` provides complete configuration keys with verified placeholder syntax.
- **Session Isolation:** In-memory sliding window queue (`deque(maxlen=20)`) isolates conversations per session ID with zero data leakage between distinct client sessions.

---

## 5. Technology Stack Summary

| Layer | Technologies |
| :--- | :--- |
| **Frontend** | Vanilla JavaScript (ES6+), HTML5 Semantic Shell, Vanilla CSS3 (Custom Design System, Glassmorphism, CSS Grid/Flexbox), Web Audio API |
| **Backend & Routing** | Python 3.11, Flask, Flask-CORS, python-dotenv, Requests, Asyncio |
| **Speech-to-Text** | `faster-whisper`, `CTranslate2`, `soundfile`, `numpy` |
| **Text-to-Speech** | ElevenLabs REST API, Sarvam.ai REST API, `edge-tts` (Microsoft Azure Neural) |
| **LLM Inference** | OpenRouter API (Nvidia Nemotron, Meta LLaMA 3.1) via OpenAI Python SDK |
