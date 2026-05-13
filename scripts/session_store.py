"""
session_store.py — Phase 4
In-memory session manager. Stores conversation history per session.
Session IDs are auto-generated UUIDs — never exposed to the user.
"""

import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from threading import Lock

MAX_HISTORY   = 6      # last N turns (1 turn = 1 user msg + 1 assistant msg)
SESSION_TTL   = 3600   # seconds before an idle session is purged (1 hour)


@dataclass
class Message:
    role: str       # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Session:
    session_id: str
    messages: deque = field(default_factory=lambda: deque(maxlen=MAX_HISTORY * 2))
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_active: datetime = field(default_factory=datetime.utcnow)

    def add(self, role: str, content: str):
        self.messages.append(Message(role=role, content=content))
        self.last_active = datetime.utcnow()

    def get_history(self) -> list[dict]:
        return [{"role": m.role, "content": m.content} for m in self.messages]

    def is_expired(self) -> bool:
        return datetime.utcnow() - self.last_active > timedelta(seconds=SESSION_TTL)


class SessionStore:
    def __init__(self):
        self._sessions: dict[str, Session] = {}
        self._lock = Lock()

    def get_or_create(self, session_id: str | None = None) -> Session:
        """Return existing session or create a new one. Auto-generates ID if None."""
        with self._lock:
            if session_id and session_id in self._sessions:
                session = self._sessions[session_id]
                if not session.is_expired():
                    return session
            # Create new session
            new_id = session_id or str(uuid.uuid4())
            session = Session(session_id=new_id)
            self._sessions[new_id] = session
            return session

    def clear(self, session_id: str) -> bool:
        with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id].messages.clear()
                return True
            return False

    def delete(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def get_history(self, session_id: str) -> list[dict] | None:
        with self._lock:
            s = self._sessions.get(session_id)
            return s.get_history() if s else None

    def purge_expired(self):
        """Remove idle sessions. Call periodically."""
        with self._lock:
            expired = [sid for sid, s in self._sessions.items() if s.is_expired()]
            for sid in expired:
                del self._sessions[sid]
        return len(expired)

    @property
    def active_count(self) -> int:
        return len(self._sessions)


# Singleton — shared across the whole app
store = SessionStore()
