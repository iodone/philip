"""wiki.graph — Analyze wiki link graph."""

from __future__ import annotations

from typing import Any

from rub.adapter import ExecutionResult
from rub.schema import Operation, OperationDetail

from philip.capabilities.wiki.config import load_config, require_vault_root, vault_paths
from philip.capabilities.wiki.graph import analyze_graph
from philip.capabilities.wiki.wiki import load_wiki_pages

# ---------------------------------------------------------------------------
# Declarative operation metadata
# ---------------------------------------------------------------------------

OPERATIONS: list[Operation] = [
    Operation(
        operation_id="wiki.graph",
        display_name="Wiki Graph",
        description="Analyze wiki link graph: communities, hubs, orphans, wanted pages",
        parameters=[],
    ),
]

DETAILS: dict[str, OperationDetail] = {
    "wiki.graph": OperationDetail(
        operation_id="wiki.graph",
        display_name="Wiki Graph",
        description=(
            "Analyze wiki link graph: communities, hub pages,"
            " orphan pages, and wanted (missing) pages."
        ),
        parameters=[],
        return_type="object",
        invocation_examples=["philip wiki.graph"],
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

    if not pages:
        return ExecutionResult(
            data={"nodes": 0, "edges": 0, "message": "No wiki pages found."}
        )

    analysis = analyze_graph(pages)

    return ExecutionResult(
        data={
            "nodes": len(analysis.nodes),
            "edges": len(analysis.edges),
            "hubs": [
                {"slug": h.slug, "connections": h.link_count + h.incoming_count}
                for h in analysis.hubs
            ],
            "communities": analysis.communities,
            "orphans": analysis.orphans,
            "wantedPages": analysis.wanted_pages,
        }
    )
