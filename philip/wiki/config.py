"""Vault configuration — discovery, parsing, path resolution."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]

try:
    import toml as _toml  # fallback for TOML writing
except ModuleNotFoundError:
    _toml = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Config model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class VaultSection:
    name: str = "My Wiki"
    language: str = "en"
    context_dir: str = "contexts"
    wiki_dir: str = "wiki"
    pages_subdir: str = "pages"


@dataclass(frozen=True)
class DB9Section:
    url: str = ""


@dataclass(frozen=True)
class WikiConfig:
    vault: VaultSection = field(default_factory=VaultSection)
    db9: DB9Section | None = None


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONFIG_PATH = ".llm-wiki/config.toml"

DEFAULT_CONFIG = WikiConfig()

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

_TEMPLATE_FILE_MAP: dict[str, str] = {
    "purpose": "purpose.md",
    "schema": "schema.md",
    "agent": "agent.md",
    "config": "config.toml",
    "log": "log.md",
    "agents_md": "AGENTS.md",
    "readme_md": "README.md",
    "rules_soul": "rules/SOUL.md",
    "rules_user": "rules/USER.md",
    "rules_communication": "rules/COMMUNICATION.md",
    "rules_security": "rules/SECURITY.md",
    "rules_workspace": "rules/WORKSPACE.md",
}


def load_template(name: str) -> str:
    """Load a built-in template file by name.

    Available names: purpose, schema, agent, config, log, agents_md,
    readme_md, rules_soul, rules_user, rules_communication,
    rules_security, rules_workspace.
    """
    rel = _TEMPLATE_FILE_MAP.get(name)
    if rel is None:
        available = ", ".join(sorted(_TEMPLATE_FILE_MAP))
        raise ValueError(f"Unknown template {name!r}. Available: {available}")
    path = _TEMPLATES_DIR / rel
    return path.read_text(encoding="utf-8").removesuffix("\n")


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def find_vault_root(from_path: str | Path = ".") -> Path | None:
    """Walk up *from_path* looking for ``.llm-wiki/config.toml``."""
    d = Path(from_path).resolve()
    while True:
        if (d / CONFIG_PATH).exists():
            return d
        parent = d.parent
        if parent == d:
            return None
        d = parent


def require_vault_root(from_path: str | Path = ".") -> Path:
    """Like :func:`find_vault_root` but raises on failure."""
    root = find_vault_root(from_path)
    if root is None:
        raise SystemExit(
            "Error: Not inside an llm-wiki vault. Run `philip wiki init` first."
        )
    return root


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _parse_toml(text: str) -> dict[str, Any]:
    """Parse TOML text, trying tomllib first, then toml fallback."""
    if tomllib is not None:
        return tomllib.loads(text)  # type: ignore[union-attr]
    if _toml is not None:
        return _toml.loads(text)  # type: ignore[union-attr]
    raise RuntimeError("No TOML parser available. Install `toml` or use Python 3.11+.")


def load_config(vault_root: str | Path) -> WikiConfig:
    """Load ``.llm-wiki/config.toml`` with defaults."""
    config_path = Path(vault_root) / CONFIG_PATH
    if not config_path.exists():
        return DEFAULT_CONFIG
    raw = config_path.read_text(encoding="utf-8")
    data = _parse_toml(raw)

    vault_raw = data.get("vault", {})
    vault = VaultSection(
        name=vault_raw.get("name", "My Wiki"),
        language=vault_raw.get("language", "en"),
        context_dir=vault_raw.get("context_dir", vault_raw.get("source_dir", "contexts")),
        wiki_dir=vault_raw.get("wiki_dir", "wiki"),
        pages_subdir=vault_raw.get("pages_subdir", "pages"),
    )

    db9_raw = data.get("db9")
    db9 = DB9Section(url=db9_raw["url"]) if db9_raw and db9_raw.get("url") else None

    return WikiConfig(vault=vault, db9=db9)


# ---------------------------------------------------------------------------
# Path computation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class VaultPaths:
    wiki: Path          # wiki/pages/ (or wiki/ if pages_subdir is empty)
    wiki_root: Path     # wiki/
    contexts: Path      # contexts/
    purpose: Path       # wiki/wiki-purpose.md
    schema: Path        # wiki/wiki-schema.md
    agent: Path         # wiki/wiki-agent.md
    log: Path           # wiki/wiki-log.md
    claude_md: Path     # CLAUDE.md
    agents_md: Path     # AGENTS.md
    rules_dir: Path     # rules/
    claude_skills_dir: Path  # .claude/skills/
    agents_skills_dir: Path  # .agents/skills/
    config: Path        # .llm-wiki/config.toml
    sync_state: Path    # .llm-wiki/sync-state.json
    llm_wiki_dir: Path  # .llm-wiki/


def vault_paths(root: str | Path, config: WikiConfig | None = None) -> VaultPaths:
    """Compute all canonical vault paths from root + config."""
    root = Path(root)
    cfg = config or DEFAULT_CONFIG
    context_dir = cfg.vault.context_dir or "contexts"
    wiki_dir = cfg.vault.wiki_dir or "wiki"
    pages_subdir = cfg.vault.pages_subdir

    wiki_root = root / wiki_dir
    wiki_pages = wiki_root / pages_subdir if pages_subdir else wiki_root

    return VaultPaths(
        wiki=wiki_pages,
        wiki_root=wiki_root,
        contexts=root / context_dir,
        purpose=wiki_root / "wiki-purpose.md",
        schema=wiki_root / "wiki-schema.md",
        agent=wiki_root / "wiki-agent.md",
        log=wiki_root / "wiki-log.md",
        claude_md=root / "CLAUDE.md",
        agents_md=root / "AGENTS.md",
        rules_dir=root / "rules",
        claude_skills_dir=root / ".claude" / "skills",
        agents_skills_dir=root / ".agents" / "skills",
        config=root / CONFIG_PATH,
        sync_state=root / ".llm-wiki" / "sync-state.json",
        llm_wiki_dir=root / ".llm-wiki",
    )
