"""Session store — maps session_id to tape/chat context."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class Session:
    """A single session bound to a tape/chat."""

    session_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)
    message_count: int = 0

    def summary(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "message_count": self.message_count,
            "metadata": self.metadata,
        }


class SessionStore:
    """In-memory session registry. First slice — no persistence."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def get_or_create(self, session_id: str) -> Session:
        """Return existing session or create a new one."""
        if session_id not in self._sessions:
            self._sessions[session_id] = Session(session_id=session_id)
        return self._sessions[session_id]

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def has(self, session_id: str) -> bool:
        return session_id in self._sessions
