"""
STT Module — Speech-to-Text using faster-whisper
Captures mic audio and transcribes it with language detection.
"""

import io
import os
import numpy as np
import sounddevice as sd
import soundfile as sf
from faster_whisper import WhisperModel
from dotenv import load_dotenv

load_dotenv()

WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL", "base")
SAMPLE_RATE = 16000
SILENCE_THRESHOLD = 0.01
SILENCE_DURATION = 1.5  # seconds of silence before stopping

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
            num_workers=2
        )
        print("[STT] Whisper model loaded ✓")
    return _model


def record_audio(max_duration: int = 30) -> np.ndarray:
    """
    Record audio from microphone with Voice Activity Detection.
    Stops after silence is detected or max_duration is reached.
    
    Returns: numpy array of audio samples.
    """
    print("[STT] 🎙️  Listening... (speak now)")
    
    recording = []
    silence_chunks = 0
    chunk_size = int(SAMPLE_RATE * 0.1)  # 100ms chunks
    max_silence_chunks = int(SILENCE_DURATION / 0.1)
    max_chunks = int(max_duration / 0.1)
    spoken = False

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


def transcribe_audio(audio: np.ndarray) -> dict:
    """
    Transcribe audio and detect language.
    
    Returns:
        dict with keys: 'text', 'language', 'confidence'
    """
    model = get_model()
    
    # Write to in-memory buffer
    buf = io.BytesIO()
    sf.write(buf, audio, SAMPLE_RATE, format="WAV")
    buf.seek(0)
    
    segments, info = model.transcribe(
        buf,
        beam_size=5,
        language=None,           # auto-detect
        condition_on_previous_text=True,
        vad_filter=True,         # voice activity detection
        vad_parameters=dict(min_silence_duration_ms=500),
    )
    
    text = " ".join([seg.text.strip() for seg in segments]).strip()
    detected_lang = info.language
    confidence = info.language_probability
    
    print(f"[STT] Transcribed: '{text}' | Lang: {detected_lang} ({confidence:.2f})")
    
    return {
        "text": text,
        "language": detected_lang,
        "confidence": confidence
    }


def transcribe_audio_bytes(audio_bytes: bytes, target_language: str = None) -> dict:
    """
    Transcribe raw audio bytes with optional target language enforcement.
    
    Args:
        audio_bytes: Raw audio bytes from web upload.
        target_language: Optional language code ('en', 'hi', 'mr') to lock Whisper.
    
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
            beam_size=5,
            language=lang_param,     # Lock language if specified
            condition_on_previous_text=False,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=300),
        )
        
        text = " ".join([seg.text.strip() for seg in segments]).strip()
        detected_lang = lang_param or info.language
        
        # Clamp foreign hallucinations (e.g. 'id', 'jw') to user selection or 'en'
        if detected_lang not in ("en", "hi", "mr"):
            detected_lang = target_language if target_language in ("en", "hi", "mr") else "en"
            
        confidence = info.language_probability
        
        print(f"[STT] Transcribed: '{text}' | Lang: {detected_lang} ({confidence:.2f})")
        
        return {
            "text": text,
            "language": detected_lang,
            "confidence": confidence
        }
    except Exception as e:
        print(f"[STT] Error transcribing: {e}")
        fallback_lang = target_language if target_language in ("en", "hi", "mr") else "en"
        return {"text": "", "language": fallback_lang, "confidence": 0.0}
