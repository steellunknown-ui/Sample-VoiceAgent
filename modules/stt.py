"""
STT Module — Speech-to-Text using faster-whisper
Optimized for low-latency cloud deployment.
"""

import io
import os
import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel
from dotenv import load_dotenv

load_dotenv()

# Use 'tiny' on cloud (0.1 CPU / 512MB RAM) for speed, 'base' locally for quality
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL", "tiny")
SAMPLE_RATE = 16000

_model = None

def get_model():
    """Lazy-load Whisper model (cached singleton)."""
    global _model
    if _model is None:
        print(f"[STT] Loading Whisper model: {WHISPER_MODEL_SIZE} ...")
        _model = WhisperModel(
            WHISPER_MODEL_SIZE,
            device="cpu",
            compute_type="int8",
            num_workers=1       # Render free tier is single-core; don't over-thread
        )
        print("[STT] Whisper model loaded [OK]")
    return _model


def record_audio(max_duration: int = 30) -> np.ndarray:
    """
    Record audio from microphone (local only - not used on cloud).
    """
    print("[STT] Recording from microphone...")
    try:
        import sounddevice as sd
    except ImportError:
        raise RuntimeError("sounddevice is not installed or audio drivers are not available.")

    SILENCE_THRESHOLD = 0.01
    SILENCE_DURATION = 1.5
    recording = []
    silence_chunks = 0
    spoken = False
    chunk_size = int(SAMPLE_RATE * 0.1)
    max_silence_chunks = int(SILENCE_DURATION / 0.1)
    max_chunks = int(max_duration / 0.1)

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32") as stream:
        for _ in range(max_chunks):
            chunk, _ = stream.read(chunk_size)
            recording.append(chunk.copy())
            rms = np.sqrt(np.mean(chunk ** 2))
            if rms > SILENCE_THRESHOLD:
                spoken = True
                silence_chunks = 0
            elif spoken:
                silence_chunks += 1
                if silence_chunks >= max_silence_chunks:
                    break

    audio = np.concatenate(recording, axis=0).flatten()
    print(f"[STT] Recorded {len(audio)/SAMPLE_RATE:.1f}s of audio")
    return audio


def transcribe_audio_bytes(audio_bytes: bytes, target_language: str = None) -> dict:
    """
    Transcribe raw audio bytes with language enforcement.
    Optimized for speed: beam_size=1, no previous text conditioning.

    Args:
        audio_bytes: Raw audio bytes from web upload.
        target_language: Language code ('en', 'hi', 'mr') to lock Whisper.

    Returns:
        dict with keys: 'text', 'language', 'confidence'
    """
    model = get_model()
    buf = io.BytesIO(audio_bytes)

    # Map language for Whisper
    lang_param = None
    if target_language in ("en", "hi", "mr"):
        lang_param = target_language
    elif target_language in ("hinglish", "urdu", "ur"):
        lang_param = "hi"

    try:
        segments, info = model.transcribe(
            buf,
            beam_size=1,                          # Greedy decode — 3-4x faster than beam_size=5
            language=lang_param,                  # Lock language — eliminates hallucinations
            condition_on_previous_text=False,     # Don't wait for context — faster cold start
            vad_filter=True,                      # Skip silent frames
            vad_parameters=dict(
                min_silence_duration_ms=400,
                speech_pad_ms=200,
            ),
            word_timestamps=False,                # Disable word timing — not needed for speed
        )

        text = " ".join([seg.text.strip() for seg in segments]).strip()
        detected_lang = lang_param or info.language

        # Clamp foreign hallucinations to user selection
        if detected_lang not in ("en", "hi", "mr"):
            detected_lang = target_language if target_language in ("en", "hi", "mr") else "en"

        confidence = info.language_probability
        safe_text = text.encode('ascii', 'replace').decode()
        print(f"[STT] Transcribed: '{safe_text}' | Lang: {detected_lang} ({confidence:.2f})")

        return {
            "text": text,
            "language": detected_lang,
            "confidence": confidence
        }
    except Exception as e:
        print(f"[STT] Error transcribing: {e}")
        fallback_lang = target_language if target_language in ("en", "hi", "mr") else "en"
        return {"text": "", "language": fallback_lang, "confidence": 0.0}
