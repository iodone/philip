"""wiki.status — Show wiki statistics and health summary."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from rub.adapter import ExecutionResult
from rub.schema import Operation, OperationDetail

from philip.capabilities.wiki.config import load_config, require_vault_root, vault_paths
from philip.capabilities.wiki.sync import load_sync_state
from philip.capabilities.wiki.wiki import list_markdown_files, load_wiki_pages

# ---------------------------------------------------------------------------
# Declarative operation metadata
# ---------------------------------------------------------------------------

OPERATIONS: list[Operation] = [
    Operation(
        operation_id="wiki.status",
        display_name="Wiki Status",
        description="Show wiki statistics and health summary",
        parameters=[],
    ),
]

DETAILS: dict[str, OperationDetail] = {
    "wiki.status": OperationDetail(
        operation_id="wiki.status",
        display_name="Wiki Status",
        description=(
            "Show wiki statistics: page count," " context count, links, health issues."
        ),
        parameters=[],
        return_type="object",
        invocation_examples=["philip wiki.status"],
    ),
}


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


def execute(args: dict[str, Any]) -> ExecutionResult:
    root = require_vault_root()
    config = load_config(root)
    paths = vault_paths(root, config)

    pages = load_wiki_pages(paths.wiki)
    context_files = list_markdown_files(paths.contexts)
    sync_state = load_sync_state(paths.sync_state)

    log_entries = 0
    if paths.log.exists():
        log_content = paths.log.read_text(encoding="utf-8")
        log_entries = len(re.findall(r"^## \[", log_content, re.MULTILINE))

    issues: list[str] = []
    for old_name, new_name in [
        ("purpose.md", "wiki-purpose.md"),
        ("schema.md", "wiki-schema.md"),
        ("log.md", "wiki-log.md"),
    ]:
        if not (root / new_name).exists() and (root / old_name).exists():
            issues.append(f"legacy {old_name} detected — rename to {new_name}")

    if not paths.purpose.exists():
        issues.append("wiki-purpose.md missing")
    if not paths.schema.exists():
        issues.append("wiki-schema.md missing")

    pages_without_contexts = [p for p in pages if not p.contexts]
    if pages_without_contexts:
        issues.append(f"{len(pages_without_contexts)} pages without contexts")

    slug_set = {p.slug.lower() for p in pages}
    broken_links = 0
    for page in pages:
        for link in page.wikilinks:
            if link.lower().removesuffix(".md") not in slug_set:
                broken_links += 1
    if broken_links:
        issues.append(f"{broken_links} broken wikilinks")

    recent_pages = sorted(pages, key=lambda p: p.mtime, reverse=True)[:5]

    return ExecutionResult(
        data={
            "wiki": config.vault.name,
            "language": config.vault.language,
            "pages": len(pages),
            "contexts": len(context_files),
            "links": sum(len(p.wikilinks) for p in pages),
            "log_entries": log_entries,
            "last_sync": sync_state.last_sync,
            "recent_pages": [
                {"date": date.fromtimestamp(p.mtime / 1000).isoformat(), "slug": p.slug}
                for p in recent_pages
            ],
            "issues": issues,
            "health": "OK" if not issues else "issues found",
        }
    )
