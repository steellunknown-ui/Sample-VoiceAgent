"""
TTS Module — Multi-Provider Text-to-Speech
Supports:
1. ElevenLabs (Hyper-realistic emotional human voices for English)
2. Sarvam.ai (Native Indian neural TTS for Hinglish, Marathi, Indian English)
3. Microsoft Edge TTS (Free, high-quality Indian neural fallback)
"""

import os
import io
import re
import base64
import asyncio
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Persistent session with retries for cloud resilience
_http_session = None

def get_http_session() -> requests.Session:
    global _http_session
    if _http_session is None:
        _http_session = requests.Session()
        retry = Retry(
            total=2,
            backoff_factor=0.3,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=4, pool_maxsize=8)
        _http_session.mount('https://', adapter)
    return _http_session
import edge_tts
from dotenv import load_dotenv

load_dotenv()

# Provider config: 'auto' | 'sarvam' | 'elevenlabs' | 'edge'
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "auto").lower()

# Sarvam.ai settings (bulbul:v3 active model)
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
SARVAM_SPEAKER = os.getenv("SARVAM_SPEAKER", "ashutosh")  # Deep male voice (options: ashutosh, aditya, rahul, rohan)

# ElevenLabs settings
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
# Default strong male voice (Adam) or any cloned voice ID
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")

# Edge-TTS fallback voices per language
EDGE_VOICES = {
    "en": os.getenv("TTS_VOICE_EN", "en-IN-NeerjaNeural"),   # Indian English
    "hi": os.getenv("TTS_VOICE_HI", "hi-IN-SwaraNeural"),    # Hindi / Hinglish
    "hinglish": os.getenv("TTS_VOICE_HI", "hi-IN-SwaraNeural"),
    "mr": os.getenv("TTS_VOICE_MR", "mr-IN-AarohiNeural"),   # Marathi
    "ur": os.getenv("TTS_VOICE_HI", "hi-IN-SwaraNeural"),
}

DEFAULT_EDGE_VOICE = EDGE_VOICES["en"]
EDGE_RATE = os.getenv("TTS_RATE", "+10%")
EDGE_PITCH = os.getenv("TTS_PITCH", "+0Hz")


def detect_response_language(text: str, detected_input_lang: str) -> str:
    """
    Determine which language to use based on user selection and text content.
    Strictly respects the user's active language selection.
    """
    if detected_input_lang in ("mr", "marathi"):
        return "mr"
    if detected_input_lang in ("hi", "hinglish", "ur", "hindi"):
        return "hi"
    if detected_input_lang in ("en", "english"):
        return "en"

    # Fallback for unknown
    deva_chars = sum(1 for c in text if "\u0900" <= c <= "\u097F")
    if deva_chars > 5:
        return "hi"
    return "en"


def _clean_for_tts(text: str) -> str:
    """Remove markdown artifacts, emojis, and symbols that sound awkward in speech."""
    # Remove markdown formatting
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"#{1,6}\s+", "", text)
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
    
    # Remove bullet points and numbers at start of lines
    text = re.sub(r"^\s*[-*•]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    
    # Remove emojis
    emoji_pattern = re.compile(
        "["
        u"\U0001F600-\U0001F64F"
        u"\U0001F300-\U0001F5FF"
        u"\U0001F680-\U0001F6FF"
        u"\U0001F1E0-\U0001F1FF"
        u"\U00002500-\U00002BEF"
        u"\U00002702-\U000027B0"
        "]+",
        flags=re.UNICODE
    )
    text = emoji_pattern.sub("", text)
    
    # Clean whitespace and linebreaks
    text = re.sub(r"\n+", ". ", text)
    text = re.sub(r"\s{2,}", " ", text)
    text = text.strip()
    
    # Credit-Saver: Keep spoken responses crisp (1-2 sentences, max 200 chars)
    # This prevents burning limited Sarvam (1k credits) or ElevenLabs (9k credits)
    if len(text) > 200:
        truncated = text[:200]
        if "." in truncated:
            text = truncated.rsplit(".", 1)[0] + "."
        else:
            text = truncated

    return text


# ── Provider 1: Sarvam.ai (Native Indian TTS) ─────────────────
def _synthesize_sarvam(text: str, lang_code: str) -> bytes:
    """
    Synthesize speech using Sarvam.ai Bulbul model.
    Superb native accents for Marathi, Hinglish, and Indian English.
    """
    if not SARVAM_API_KEY or SARVAM_API_KEY.startswith("your_"):
        return None
    
    target_lang_map = {
        "mr": "mr-IN",
        "hi": "hi-IN",
        "hinglish": "hi-IN",
        "en": "en-IN"
    }
    target_lang = target_lang_map.get(lang_code, "en-IN")
    
    try:
        print(f"[TTS-Sarvam] ({len(text)} chars) Requesting {target_lang} with speaker '{SARVAM_SPEAKER}'...")
        url = "https://api.sarvam.ai/text-to-speech"
        headers = {
            "api-subscription-key": SARVAM_API_KEY,
            "Content-Type": "application/json"
        }
        payload = {
            "inputs": [text],
            "target_language_code": target_lang,
            "speaker": SARVAM_SPEAKER,
            "pitch": 0,
            "pace": 1.05,
            "loudness": 1.5,
            "speech_sample_rate": 22050,
            "enable_preprocessing": True,
            "model": "bulbul:v3"
        }
        
        resp = get_http_session().post(url, headers=headers, json=payload, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            audios = data.get("audios", [])
            if audios and audios[0]:
                audio_bytes = base64.b64decode(audios[0])
                print(f"[TTS-Sarvam] [OK] Success ({len(audio_bytes)} bytes WAV)")
                return audio_bytes
        elif resp.status_code in (401, 402, 429):
            print(f"[TTS-Sarvam] [WARN] Quota or credit limit reached ({resp.status_code}). Seamlessly using free Edge-TTS fallback.")
        else:
            print(f"[TTS-Sarvam] [WARN] ({resp.status_code}): {resp.text[:150]}")
    except Exception as e:
        print(f"[TTS-Sarvam] Exception: {e}")
    
    return None


# ── Provider 2: ElevenLabs (Expressive Human English) ──────────
def _synthesize_elevenlabs(text: str) -> bytes:
    """
    Synthesize speech using ElevenLabs multilingual v2.
    Studio-grade human realism and emotional delivery.
    """
    if not ELEVENLABS_API_KEY or ELEVENLABS_API_KEY.startswith("your_"):
        return None
    
    try:
        print(f"[TTS-ElevenLabs] ({len(text)} chars) Requesting voice {ELEVENLABS_VOICE_ID}...")
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
        headers = {
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg"
        }
        payload = {
            "text": text,
            "model_id": "eleven_turbo_v2_5",   # Fastest ElevenLabs model (~300ms vs ~1.5s)
            "voice_settings": {
                "stability": 0.45,
                "similarity_boost": 0.70,
                "style": 0.0,
                "use_speaker_boost": False      # Disable to save latency
            },
            "optimize_streaming_latency": 3     # Max latency optimization
        }
        
        resp = get_http_session().post(url, headers=headers, json=payload, timeout=15)
        if resp.status_code == 200 and resp.content:
            print(f"[TTS-ElevenLabs] [OK] Success ({len(resp.content)} bytes MP3)")
            return resp.content
        elif resp.status_code in (401, 402, 429):
            print(f"[TTS-ElevenLabs] [WARN] Quota or credit limit reached ({resp.status_code}). Seamlessly using free Edge-TTS fallback.")
        else:
            print(f"[TTS-ElevenLabs] [WARN] ({resp.status_code}): {resp.text[:150]}")
    except Exception as e:
        print(f"[TTS-ElevenLabs] Exception: {e}")
    
    return None


# ── Provider 3: Microsoft Edge TTS (Free Indian Neural Voices) ─
async def _synthesize_edge_async(text: str, voice: str) -> bytes:
    """Edge TTS async core synthesis."""
    communicate = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate=EDGE_RATE,
        pitch=EDGE_PITCH,
        volume="+0%"
    )
    chunks = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])
    return b"".join(chunks)


def _synthesize_edge(text: str, lang_code: str) -> bytes:
    """Synthesize with Edge TTS using Indian neural voice."""
    voice = EDGE_VOICES.get(lang_code, DEFAULT_EDGE_VOICE)
    print(f"[TTS-Edge] Speaking with voice: {voice}")
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        audio_bytes = loop.run_until_complete(_synthesize_edge_async(text, voice))
        loop.close()
        return audio_bytes
    except Exception as e:
        print(f"[TTS-Edge] Error: {e}")
        return b""


# ── Public Synthesis Dispatcher ──────────────────────────────
def synthesize_speech(
    text: str,
    detected_language: str = "en"
) -> tuple[bytes, str]:
    """
    Main TTS entry point with strict user model mapping & fallback:
    - English -> ElevenLabs (Adam) -> Fallback to Edge-TTS
    - Hinglish / Marathi -> Sarvam.ai (Ashutosh) -> Fallback to Edge-TTS
    
    Returns:
        tuple: (audio_bytes, provider_label)
    """
    clean_text = _clean_for_tts(text)
    if not clean_text:
        return b"", "None"
    
    lang_key = detect_response_language(clean_text, detected_language)
    audio = None
    provider_used = "Edge-TTS (Fallback)"
    
    # English -> Strictly ElevenLabs with Edge-TTS Fallback
    if lang_key == "en":
        if ELEVENLABS_API_KEY:
            audio = _synthesize_elevenlabs(clean_text)
            if audio:
                voice_name = "George" if ELEVENLABS_VOICE_ID == "JBFqnCBsd6RMkjVDRZzb" else ("Adam" if ELEVENLABS_VOICE_ID == "pNInz6obpgDQGcFmaJgB" else "Custom")
                provider_used = f"ElevenLabs ({voice_name})"
        
        # Fallback to Edge-TTS Indian English Male
        if not audio:
            audio = _synthesize_edge(clean_text, "en")
            provider_used = "Edge-TTS (Fallback)"
            
    # Hinglish & Marathi -> Strictly Sarvam.ai with Edge-TTS Fallback
    else:
        if SARVAM_API_KEY:
            audio = _synthesize_sarvam(clean_text, lang_key)
            if audio:
                provider_used = "Sarvam.ai (Ashutosh)"
        
        # Fallback to Edge-TTS Indian Male / Marathi
        if not audio:
            audio = _synthesize_edge(clean_text, lang_key)
            provider_used = "Edge-TTS (Fallback)"
    
    print(f"[TTS] Complete via {provider_used}: {len(audio) if audio else 0} bytes")
    return audio or b"", provider_used
