"""
app.py — Flask Backend Server for the Voice Agent
Handles audio uploads, processes through STT -> LLM -> TTS pipeline,
and returns audio responses to the web UI.
"""

import sys
import io
# Fix Windows console encoding (supports Unicode output)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import os
import base64
import uuid
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from dotenv import load_dotenv

# Import our modules
from modules.stt import transcribe_audio_bytes, get_model as get_stt_model
from modules.llm import get_llm_response
from modules.tts import synthesize_speech
from modules.conversation import get_session, clear_session, get_all_sessions

load_dotenv()

# ── App Setup ────────────────────────────────────────────────
app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app)

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 5000))
AGENT_NAME = os.getenv("AGENT_NAME", "Aria")

# ── Routes ───────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the main web UI."""
    return send_from_directory("static", "index.html")


@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint."""
    api_key_set = bool(
        os.getenv("OPENROUTER_API_KEY") and 
        os.getenv("OPENROUTER_API_KEY") != "your_openrouter_api_key_here"
    )
    sarvam_set = bool(os.getenv("SARVAM_API_KEY"))
    eleven_set = bool(os.getenv("ELEVENLABS_API_KEY"))
    
    return jsonify({
        "status": "ok",
        "agent": AGENT_NAME,
        "model": os.getenv("OPENROUTER_MODEL", "not configured"),
        "api_key_configured": api_key_set,
        "tts_provider": os.getenv("TTS_PROVIDER", "auto"),
        "sarvam_configured": sarvam_set,
        "elevenlabs_configured": eleven_set,
        "message": "Voice Agent is running! 🎙️" if api_key_set else "⚠️ API key not configured"
    })


@app.route("/api/chat/voice", methods=["POST"])
def chat_voice():
    """
    Main voice pipeline endpoint.
    Accepts: multipart/form-data with 'audio' file + 'session_id'
    Returns: JSON with transcription, response text, and base64 audio
    """
    # Get session and target language
    session_id = request.form.get("session_id", "default")
    target_lang = request.form.get("language", "en")
    session = get_session(session_id)
    
    # Get audio file
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400
    
    audio_file = request.files["audio"]
    audio_bytes = audio_file.read()
    
    if not audio_bytes:
        return jsonify({"error": "Empty audio file"}), 400
    
    try:
        # ── Step 1: Speech-to-Text with Language Enforcement ──
        stt_result = transcribe_audio_bytes(audio_bytes, target_language=target_lang)
        user_text = stt_result["text"]
        detected_lang = target_lang if target_lang in ("en", "hi", "mr") else stt_result["language"]
        
        if not user_text.strip():
            return jsonify({
                "error": "Could not understand audio. Please speak clearly.",
                "transcription": "",
                "response_text": "",
                "audio_base64": "",
                "language": detected_lang,
                "provider": "None"
            }), 200
        
        # ── Step 2: Add to conversation history ───────────────
        session.add_user_message(user_text, detected_lang)
        
        # ── Step 3: LLM Response ─────────────────────────────
        history = session.get_history()[:-1]
        response_text = get_llm_response(
            user_message=user_text,
            conversation_history=history,
            detected_language=detected_lang
        )
        
        # Add response to history
        session.add_assistant_message(response_text)
        
        # ── Step 4: Text-to-Speech (ElevenLabs for EN, Sarvam for HI/MR)
        audio_bytes_response, provider = synthesize_speech(response_text, detected_lang)
        audio_base64 = base64.b64encode(audio_bytes_response).decode("utf-8")
        
        return jsonify({
            "transcription": user_text,
            "response_text": response_text,
            "audio_base64": audio_base64,
            "language": detected_lang,
            "provider": provider,
            "session_id": session_id,
            "turn": session.turn_count
        })
        
    except ValueError as e:
        # API key not configured
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        print(f"[Server] Error in pipeline: {e}")
        return jsonify({"error": f"Processing error: {str(e)}"}), 500


@app.route("/api/chat/text", methods=["POST"])
def chat_text():
    """
    Text-only chat endpoint (for testing without mic).
    Accepts: JSON with 'message', 'session_id', 'language'
    Returns: JSON with response text and base64 audio
    """
    data = request.get_json()
    
    if not data or "message" not in data:
        return jsonify({"error": "No message provided"}), 400
    
    user_text = data["message"].strip()
    session_id = data.get("session_id", "default")
    detected_lang = data.get("language", "en")
    
    if not user_text:
        return jsonify({"error": "Empty message"}), 400
    
    session = get_session(session_id)
    
    try:
        # Add to history
        session.add_user_message(user_text, detected_lang)
        history = session.get_history()[:-1]
        
        # LLM response
        response_text = get_llm_response(
            user_message=user_text,
            conversation_history=history,
            detected_language=detected_lang
        )
        session.add_assistant_message(response_text)
        
        # TTS
        audio_bytes, provider = synthesize_speech(response_text, detected_lang)
        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
        
        return jsonify({
            "transcription": user_text,
            "response_text": response_text,
            "audio_base64": audio_base64,
            "language": detected_lang,
            "provider": provider,
            "session_id": session_id,
            "turn": session.turn_count
        })
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        print(f"[Server] Text chat error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/session/clear", methods=["POST"])
def clear_session_route():
    """Clear conversation history for a session."""
    data = request.get_json() or {}
    session_id = data.get("session_id", "default")
    clear_session(session_id)
    return jsonify({"status": "cleared", "session_id": session_id})


@app.route("/api/session/stats", methods=["GET"])
def session_stats():
    """Get stats for all active sessions."""
    return jsonify({"sessions": get_all_sessions()})


# ── Startup ──────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"""
===========================================
  Voice Agent: {AGENT_NAME}
  Multilingual: EN + Hinglish + Marathi
===========================================

  Server starting on http://localhost:{PORT}
  Open browser: http://localhost:{PORT}

  STT model: lazy-load on first request (saves RAM)
""")
    app.run(host=HOST, port=PORT, debug=False, threaded=True)
