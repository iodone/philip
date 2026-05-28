"""Wiki page model — parsing, wikilink extraction, page loading."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

try:
    import frontmatter  # python-frontmatter
except ModuleNotFoundError:
    frontmatter = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Wikilink regex
# ---------------------------------------------------------------------------

# Matches [[target]] and [[target|display text]]
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")


def extract_wikilinks(content: str) -> list[str]:
    """Extract unique wikilink targets from markdown *content*."""
    return list(
        dict.fromkeys(m.group(1).strip() for m in _WIKILINK_RE.finditer(content))
    )


# ---------------------------------------------------------------------------
# WikiPage model
# ---------------------------------------------------------------------------


@dataclass
class WikiPage:
    path: Path
    relative_path: str
    slug: str
    title: str
    description: str | None = None
    tags: list[str] = field(default_factory=list)
    contexts: list[str] = field(default_factory=list)
    created: str | None = None
    updated: str | None = None
    aliases: list[str] = field(default_factory=list)
    content: str = ""
    wikilinks: list[str] = field(default_factory=list)
    mtime: float = 0.0


# ---------------------------------------------------------------------------
# YAML frontmatter parsing
# ---------------------------------------------------------------------------


def _parse_frontmatter(text: str) -> tuple[dict[str, object], str]:
    """Parse YAML frontmatter from markdown text.

    Returns ``(metadata_dict, body_content)``.
    """
    if frontmatter is not None:
        post = frontmatter.loads(text)
        return dict(post.metadata), post.content

    # Fallback: manual parsing when python-frontmatter is not installed
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            _empty, yaml_text, body = parts
            try:
                import yaml

                meta = yaml.safe_load(yaml_text) or {}
            except (ModuleNotFoundError, Exception):
                meta = {}
            return meta, body.lstrip("\n")
    return {}, text


# ---------------------------------------------------------------------------
# Page loading
# ---------------------------------------------------------------------------


def list_markdown_files(directory: str | Path) -> list[Path]:
    """Recursively list ``*.md`` files under *directory*."""
    d = Path(directory)
    if not d.exists():
        return []
    return sorted(p for p in d.rglob("*.md") if p.is_file())


def parse_wiki_page(file_path: str | Path, wiki_dir: str | Path) -> WikiPage:
    """Parse a single markdown file into a :class:`WikiPage`."""
    file_path = Path(file_path)
    wiki_dir = Path(wiki_dir)
    raw = file_path.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(raw)
    stat = file_path.stat()
    rel = str(file_path.relative_to(wiki_dir))
    slug = rel.removesuffix(".md")

    tags = meta.get("tags", [])
    if not isinstance(tags, list):
        tags = []
    contexts = meta.get("contexts", [])
    if not isinstance(contexts, list):
        contexts = []
    aliases = meta.get("aliases", [])
    if not isinstance(aliases, list):
        aliases = []

    return WikiPage(
        path=file_path,
        relative_path=rel,
        slug=slug,
        title=str(meta.get("title", file_path.stem)),
        description=meta.get("description"),
        tags=tags,
        contexts=contexts,
        created=meta.get("created"),
        updated=meta.get("updated"),
        aliases=aliases,
        content=body,
        wikilinks=extract_wikilinks(body),
        mtime=stat.st_mtime * 1000,  # match JS mtimeMs
    )


def load_wiki_pages(wiki_dir: str | Path) -> list[WikiPage]:
    """Load all wiki pages from a directory."""
    return [parse_wiki_page(f, wiki_dir) for f in list_markdown_files(wiki_dir)]
