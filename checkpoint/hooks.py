"""Checkpoint system stubs for git-claw v4."""
from __future__ import annotations
from pathlib import Path

_current_session_id: str | None = None
_tracked_edits: dict[str, str | None] = {}

def set_session(session_id: str) -> None:
    global _current_session_id
    _current_session_id = session_id

def get_tracked_edits() -> dict[str, str | None]:
    return dict(_tracked_edits)

def reset_tracked() -> None:
    _tracked_edits.clear()

def install_hooks() -> None:
    """No-op checkpoint hooks for git-claw (we use git for rollback)."""
    pass
