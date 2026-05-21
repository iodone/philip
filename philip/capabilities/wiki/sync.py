"""Sync state tracking — mtime + SHA-256 content hashing."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from philip.capabilities.wiki.wiki import list_markdown_files


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class SyncEntry:
    path: str
    mtime: float
    content_hash: str
    last_synced: str


@dataclass
class SyncState:
    entries: dict[str, SyncEntry] = field(default_factory=dict)
    last_sync: str = ""


@dataclass
class SyncResult:
    added: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def load_sync_state(state_path: str | Path) -> SyncState:
    """Load sync state from JSON file."""
    p = Path(state_path)
    if not p.exists():
        return SyncState()
    data = json.loads(p.read_text(encoding="utf-8"))
    entries = {}
    for rel, entry_data in data.get("entries", {}).items():
        entries[rel] = SyncEntry(**entry_data)
    return SyncState(entries=entries, last_sync=data.get("last_sync", ""))


def save_sync_state(state_path: str | Path, state: SyncState) -> None:
    """Save sync state to JSON file."""
    p = Path(state_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "entries": {
            rel: {
                "path": e.path,
                "mtime": e.mtime,
                "content_hash": e.content_hash,
                "last_synced": e.last_synced,
            }
            for rel, e in state.entries.items()
        },
        "last_sync": state.last_sync,
    }
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Content hashing
# ---------------------------------------------------------------------------

def content_hash(file_path: str | Path) -> str:
    """SHA-256 of file content, truncated to first 16 hex chars."""
    data = Path(file_path).read_bytes()
    return hashlib.sha256(data).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Sync computation
# ---------------------------------------------------------------------------

def compute_sync(
    dirs: list[str | Path],
    base_dir: str | Path,
    state: SyncState,
) -> SyncResult:
    """Compare current file state against saved sync state."""
    result = SyncResult()
    current_files: set[str] = set()
    base = Path(base_dir)

    for d in dirs:
        for file_path in list_markdown_files(d):
            rel = str(file_path.relative_to(base))
            current_files.add(rel)
            existing = state.entries.get(rel)

            if existing is None:
                result.added.append(rel)
            elif file_path.stat().st_mtime * 1000 != existing.mtime:
                # mtime changed, check content hash
                h = content_hash(file_path)
                if h != existing.content_hash:
                    result.modified.append(rel)
                else:
                    result.unchanged.append(rel)
            else:
                result.unchanged.append(rel)

    # Check for deleted files
    for rel in state.entries:
        if rel not in current_files:
            result.deleted.append(rel)

    return result


def update_sync_state(
    dirs: list[str | Path],
    base_dir: str | Path,
    state: SyncState,
) -> SyncState:
    """Update sync state with current file metadata."""
    new_entries: dict[str, SyncEntry] = {}
    base = Path(base_dir)
    today = date.today().isoformat()

    for d in dirs:
        for file_path in list_markdown_files(d):
            rel = str(file_path.relative_to(base))
            st = file_path.stat()
            new_entries[rel] = SyncEntry(
                path=rel,
                mtime=st.st_mtime * 1000,
                content_hash=content_hash(file_path),
                last_synced=today,
            )

    return SyncState(entries=new_entries, last_sync=today)
