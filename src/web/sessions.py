"""In-memory session store for Alfred conversations."""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from alfred.memory.conversation import initialize_conversation

SESSION_TTL = 7200  # 2 hours


@dataclass
class Session:
    session_id: str
    user_id: str
    conversation: Any  # alfred Conversation object (opaque)
    messages: list[dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)

    def touch(self) -> None:
        self.last_active = time.time()

    def reset_conversation(self) -> None:
        self.conversation = initialize_conversation()
        self.messages.clear()


# Global session store: session_id -> Session
_sessions: dict[str, Session] = {}


def create_session(user_id: str) -> Session:
    sid = uuid.uuid4().hex
    session = Session(
        session_id=sid,
        user_id=user_id,
        conversation=initialize_conversation(),
    )
    _sessions[sid] = session
    return session


def get_session(session_id: str) -> Session | None:
    session = _sessions.get(session_id)
    if session is None:
        return None
    if time.time() - session.last_active > SESSION_TTL:
        _sessions.pop(session_id, None)
        return None
    session.touch()
    return session


def delete_session(session_id: str) -> None:
    _sessions.pop(session_id, None)


def cleanup_expired() -> int:
    """Remove expired sessions. Returns count removed."""
    now = time.time()
    expired = [sid for sid, s in _sessions.items() if now - s.last_active > SESSION_TTL]
    for sid in expired:
        del _sessions[sid]
    return len(expired)
