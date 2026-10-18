# 🎙️ Aria AI — Enterprise Multilingual Voice Console

> **English · Hinglish · Marathi** — Real-time AI Voice Assistant with strict multi-provider speech routing, Hands-Free Voice Activity Detection, and Zero-Downtime Fallbacks.

---

## ✨ Key Features

- 🇬🇧 **English (ElevenLabs):** Studio-grade emotional human voice synthesis via ElevenLabs (`George` / `Adam`).
- 🇮🇳 **Hinglish & Marathi (Sarvam.ai):** Native Indian neural voices via Sarvam AI `bulbul:v3` (`Ashutosh`).
- 🛡️ **Zero-Downtime Fallback (Edge-TTS):** Automatic failover to free Microsoft Indian Neural voices if API quotas/credit limits are reached.
- ⚡ **Hands-Free Live Mode:** Browser-side Voice Activity Detection (VAD) with automatic silence cutoff and turn-taking (ChatGPT/Gemini live style).
- 🔘 **Push-to-Talk Mode:** Manual microphone control with single-click recording.
- 🧠 **Context-Aware LLM:** Powered by free OpenRouter models (Nvidia Nemotron, LLaMA 3.1) with conversation memory and respectful moderation.
- 🎨 **Bespoke Executive UI:** Obsidian navy & cobalt aesthetic with dynamic ambient pulse orb and audio waveform visualizer.

---

## 🏗️ Architecture

```
User Voice (Browser Mic)
   │
   ▼
Flask API Server (Local / Remote)
   │
   ├── Speech-to-Text: faster-whisper (Strict language locking: en, hi, mr)
   │
   ├── Language Intelligence: OpenRouter (Nemotron / LLaMA)
   │
   └── Text-to-Speech Engine Dispatcher:
         ├── English            ──► ElevenLabs API (George / Adam)
         ├── Hinglish & Marathi ──► Sarvam.ai API (Ashutosh / bulbul:v3)
         └── Quota/Error Guard  ──► Edge-TTS Fallback (Free Neural)
```

---

## 🚀 Quick Start

### 1. Clone & Setup

```bash
git clone <YOUR_REPO_URL>
cd Sample-Voiceagent
```

### 2. Configure Environment

Copy the template and add your API keys:

```bash
cp .env.example .env
```

Edit `.env`:
```dotenv
# Required for AI responses
OPENROUTER_API_KEY=your_openrouter_key_here

# For English Voice (ElevenLabs)
ELEVENLABS_API_KEY=your_elevenlabs_key_here
ELEVENLABS_VOICE_ID=JBFqnCBsd6RMkjVDRZzb

# For Hinglish & Marathi Voice (Sarvam.ai)
SARVAM_API_KEY=your_sarvam_key_here
SARVAM_SPEAKER=ashutosh
```

> **Security Note:** `.env` is included in `.gitignore` and must **never** be committed to public repositories.

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the Server

```bash
python app.py
```

Open your browser at:
```
http://localhost:5000
```

---

## 📁 Project Structure

```
Sample-Voiceagent/
├── app.py                    # Flask server & audio API endpoints
├── requirements.txt          # Python dependencies
├── .env.example              # Safe configuration template (NO SECRETS)
├── .gitignore                # Git ignore rules protecting .env and cache
├── README.md                 # Project documentation
├── setup.ps1                 # Windows PowerShell setup script
├── modules/
│   ├── stt.py                # Speech-to-Text (faster-whisper)
│   ├── llm.py                # LLM orchestration & prompt guardrails (OpenRouter)
│   ├── tts.py                # Multi-provider TTS (ElevenLabs, Sarvam, Edge)
│   └── conversation.py       # Multi-turn conversation context manager
└── static/
    ├── index.html            # Bespoke executive voice console
    ├── style.css             # Dark cobalt design system
    └── app.js                # VAD audio processing & frontend controller
```

---

## 🛡️ License

MIT License. Free for personal and commercial exploration.
