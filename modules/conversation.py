"""
Conversation Manager — Manages session history and context.
"""

from collections import deque
from datetime import datetime


class ConversationManager:
    """
    Manages conversation history with context window limiting.
    Keeps the last N exchanges to stay within token limits.
    """
    
    MAX_HISTORY = 10  # Max number of turns (user+assistant pairs) to keep
    
    def __init__(self, session_id: str = "default"):
        self.session_id = session_id
        self.history = deque(maxlen=self.MAX_HISTORY * 2)  # *2 for user+assistant
        self.created_at = datetime.now()
        self.turn_count = 0
        self.detected_language = "en"
    
    def add_user_message(self, text: str, language: str = "en"):
        """Add a user message to history."""
        self.history.append({"role": "user", "content": text})
        self.detected_language = language
        self.turn_count += 1
    
    def add_assistant_message(self, text: str):
        """Add an assistant response to history."""
        self.history.append({"role": "assistant", "content": text})
    
    def get_history(self) -> list:
        """Get the conversation history as a list."""
        return list(self.history)
    
    def clear(self):
        """Clear conversation history."""
        self.history.clear()
        self.turn_count = 0
        print(f"[Session {self.session_id}] Conversation cleared.")
    
    def get_stats(self) -> dict:
        """Get session statistics."""
        return {
            "session_id": self.session_id,
            "turn_count": self.turn_count,
            "history_length": len(self.history),
            "created_at": self.created_at.isoformat(),
            "last_language": self.detected_language
        }


# Global session store (in-memory; replace with Redis for production)
_sessions: dict[str, ConversationManager] = {}


def get_session(session_id: str = "default") -> ConversationManager:
    """Get or create a conversation session."""
    if session_id not in _sessions:
        _sessions[session_id] = ConversationManager(session_id)
        print(f"[Session] New session created: {session_id}")
    return _sessions[session_id]


def clear_session(session_id: str = "default"):
    """Clear a specific session."""
    if session_id in _sessions:
        _sessions[session_id].clear()


def get_all_sessions() -> list:
    """List all active sessions."""
    return [mgr.get_stats() for mgr in _sessions.values()]
