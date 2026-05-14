# session_store.py — per-profile conversation memory

import time
import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple


@dataclass
class Message:
    role: str  # "user" or "assistant"
    content: str
    ts: float = field(default_factory=time.time)


@dataclass
class Session:
    id: str
    profile: str
    messages: List[Message] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_used_at: float = field(default_factory=time.time)
    ttl_seconds: int = 60 * 60  # 1 hour

    def add(self, role: str, content: str):
        self.messages.append(Message(role=role, content=content))
        self.last_used_at = time.time()

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.last_used_at) > self.ttl_seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "profile": self.profile,
            "messages": [
                {"role": m.role, "content": m.content, "ts": m.ts}
                for m in self.messages
            ],
            "created_at": self.created_at,
            "last_used_at": self.last_used_at,
        }


class SessionStore:
    """
    Stores sessions keyed by (profile, session_id) so each profile
    has its own independent conversation history.
    """

    def __init__(self):
        self._sessions: Dict[Tuple[str, str], Session] = {}

    def _key(self, profile: str, session_id: str) -> Tuple[str, str]:
        return (profile, session_id)

    def get_or_create(self, profile: str, session_id: str | None = None) -> Session:
        if not session_id:
            session_id = uuid.uuid4().hex

        key = self._key(profile, session_id)
        if key not in self._sessions:
            self._sessions[key] = Session(id=session_id, profile=profile)
        return self._sessions[key]

    def get(self, profile: str, session_id: str) -> Session | None:
        return self._sessions.get(self._key(profile, session_id))

    def clear(self, profile: str, session_id: str) -> None:
        self._sessions.pop(self._key(profile, session_id), None)

    def cleanup_expired(self) -> None:
        to_delete = [k for k, s in self._sessions.items() if s.is_expired]
        for k in to_delete:
            del self._sessions[k]

    @property
    def active_count(self) -> int:
        return len(self._sessions) 