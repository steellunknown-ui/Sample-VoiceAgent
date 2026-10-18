"""
LLM Module — Language Model via OpenRouter API
Handles conversation history, language-aware prompting,
and inappropriate content filtering.
"""

import os
import httpx
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct:free")
AGENT_NAME = os.getenv("AGENT_NAME", "Aria")

# ==============================================================
# SYSTEM PROMPT — The core personality of the agent
# ==============================================================

SYSTEM_PROMPT = f"""You are {AGENT_NAME}, a smart, friendly, and professional voice assistant.

🌍 LANGUAGE RULES (CRITICAL):
- Detect the language of the user's message automatically.
- If user speaks in English → reply in natural, professional English.
- If user speaks in Hinglish (Hindi + English mix) → reply in Hinglish naturally. 
  Example: "Haan bilkul, main aapki help kar sakta hoon. Koi bhi question ho toh batao!"
- If user speaks in Marathi → reply in Marathi naturally.
  Example: "हो, मी तुम्हाला नक्कीच मदत करेन. काय प्रश्न आहे?"
- NEVER switch language unless the user switches first.

🎯 PERSONALITY:
- Professional yet warm and friendly.
- Speak naturally like a real human, NOT like a robot.
- Be concise — voice responses must be 1-2 short sentences max (under 140 characters).
- Use natural filler words when appropriate (e.g., "Sure!", "Great question!").
- Show empathy when needed ("I understand, that can be tricky...").

📚 EXPERTISE:
- Daily conversations (greetings, small talk, general queries).
- Tech support (basic to intermediate: phones, laptops, apps, internet, software).
- General knowledge and problem-solving.
- Scheduling, reminders, and productivity tips.

🚫 INAPPROPRIATE CONTENT RULES:
- If user asks anything offensive, abusive, sexual, violent, or harmful → respond with a FIRM, PROFESSIONAL scold.
- Do NOT answer inappropriate questions under any circumstance.
- Scold example (English): "I'm sorry, but that kind of question is completely inappropriate. Please keep our conversation respectful."
- Scold example (Hinglish): "Dekho yaar, aisa sawaal poochna bilkul galat hai. Please thoda respect ke saath baat karo."
- Scold example (Marathi): "असे प्रश्न विचारणे अयोग्य आहे. कृपया आदराने बोला."

💡 RESPONSE FORMAT:
- Keep responses SHORT and SPOKEN (1-2 sentences max, under 140 chars) — no bullet points, no markdown, no emojis.
- Sound like you're actually talking, not typing.
"""

# ==============================================================

_client = None

def get_client() -> OpenAI:
    """Lazy-load OpenAI-compatible client for OpenRouter."""
    global _client
    if _client is None:
        if not OPENROUTER_API_KEY or OPENROUTER_API_KEY == "your_openrouter_api_key_here":
            raise ValueError(
                "❌ OpenRouter API key not set! "
                "Please copy .env.example to .env and add your API key from https://openrouter.ai"
            )
        _client = OpenAI(
            api_key=OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            http_client=httpx.Client(),
            default_headers={
                "HTTP-Referer": "https://voice-agent.local",
                "X-Title": f"{AGENT_NAME} Voice Agent",
            }
        )
    return _client


FALLBACK_MODELS = [
    "nvidia/nemotron-3-super-120b-a12b:free",
    "liquid/lfm-2.5-2.6b:free",
    "openrouter/free"
]


def get_llm_response(
    user_message: str,
    conversation_history: list,
    detected_language: str = "en"
) -> str:
    """
    Get a response from the LLM given the user message and history.
    Tries primary model first, with automatic fallback if rate-limited.
    
    Args:
        user_message: The transcribed user speech.
        conversation_history: List of {"role": ..., "content": ...} dicts.
        detected_language: Language code from STT (e.g., 'en', 'hi', 'mr').
    
    Returns:
        str: The agent's response text.
    """
    client = get_client()
    
    # Language hint injection for better accuracy
    lang_hint = ""
    if detected_language in ("hi", "ur"):
        lang_hint = "\n[CRITICAL: User is speaking in Hinglish. Reply in natural Hinglish — Hindi mixed with English.]"
    elif detected_language == "mr":
        lang_hint = "\n[CRITICAL: User is speaking in Marathi. Reply in Marathi script directly.]"
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + lang_hint}
    ] + conversation_history + [
        {"role": "user", "content": user_message}
    ]
    
    # Prioritize configured model, followed by fallbacks
    models_to_try = [OPENROUTER_MODEL] + [m for m in FALLBACK_MODELS if m != OPENROUTER_MODEL]
    
    last_error = ""
    for model_name in models_to_try:
        try:
            print(f"[LLM] Calling {model_name} ...")
            
            # Use reasoning: effort: none to eliminate thinking delays for voice
            extra_params = {}
            if "nemotron" in model_name or "liquid" in model_name:
                extra_params["extra_body"] = {"reasoning": {"effort": "none"}}

            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                max_tokens=120,         # Keep responses crisp (1-2 sentences) to save voice credits
                temperature=0.7,        # Natural, warm conversational
                top_p=0.9,
                timeout=12,             # Fast failover if model is slow
                **extra_params
            )
            
            msg = response.choices[0].message
            reply = msg.content or getattr(msg, "reasoning", "") or ""
            reply = reply.strip()
            
            if reply:
                print(f"[LLM] Response from {model_name}: '{reply[:100]}...' " if len(reply) > 100 else f"[LLM] Response: '{reply}'")
                return reply
            else:
                print(f"[LLM] Empty response from {model_name}, trying fallback...")
                continue
                
        except Exception as e:
            last_error = str(e)
            print(f"[LLM] Error with {model_name}: {last_error}")
            continue

    # If all models failed:
    if "401" in last_error or "authentication" in last_error.lower():
        return "I'm sorry, there seems to be an API authentication issue. Please check the API key configuration."
    elif "429" in last_error or "rate limit" in last_error.lower():
        return "I'm experiencing high demand right now. Please give me a quick moment and try again."
    else:
        return "I'm sorry, I ran into a small glitch. Could you please say that again?"
