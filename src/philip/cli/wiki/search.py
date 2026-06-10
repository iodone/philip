"""wiki.search — Search wiki pages (BM25 + grep)."""

from __future__ import annotations

from typing import Any

from rub.adapter import ExecutionResult
from rub.errors import InvalidArgumentsError
from rub.schema import Operation, OperationDetail, Parameter

from philip.capabilities.wiki.config import load_config, require_vault_root, vault_paths
from philip.capabilities.wiki.search import bm25_search, grep_search, rrf_merge
from philip.capabilities.wiki.wiki import load_wiki_pages

# ---------------------------------------------------------------------------
# Declarative operation metadata
# ---------------------------------------------------------------------------

OPERATIONS: list[Operation] = [
    Operation(
        operation_id="wiki.search",
        display_name="Wiki Search",
        description="Search wiki pages (BM25 + ripgrep)",
        parameters=[
            Parameter(
                name="query",
                param_type="string",
                required=True,
                description="Search query",
            ),
            Parameter(
                name="limit",
                param_type="integer",
                default=10,
                description="Max results",
            ),
        ],
    ),
]

DETAILS: dict[str, OperationDetail] = {
    "wiki.search": OperationDetail(
        operation_id="wiki.search",
        display_name="Wiki Search",
        description="Search wiki pages using BM25 ranking + ripgrep exact match.",
        parameters=OPERATIONS[0].parameters,
        return_type="object",
        invocation_examples=[
            "philip wiki.search query=machine learning",
            "philip wiki.search query=test limit=5",
        ],
    ),
}


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


def execute(args: dict[str, Any]) -> ExecutionResult:
    query = args.get("query")
    if not query:
        raise InvalidArgumentsError("Missing required parameter: query")

    limit = int(args.get("limit", 10))

    root = require_vault_root()
    config = load_config(root)
    paths = vault_paths(root, config)
    pages = load_wiki_pages(paths.wiki)

    if not pages:
        return ExecutionResult(
            data={"mode": "none", "results": [], "message": "No wiki pages found."}
        )

    pages_by_slug = {p.slug: p for p in pages}

    # BM25 — fuzzy ranked search
    bm25_results = bm25_search(pages, query, limit * 2)

    # Grep — exact/regex search via ripgrep
    grep_results = grep_search(str(paths.wiki), query, limit * 2)

    # Merge or fallback
    bm25_dicts = [{"slug": r.page.slug, "score": r.score} for r in bm25_results]
    grep_dicts = [{"slug": r.page.slug, "score": r.score} for r in grep_results]

    if grep_dicts:
        final_results = rrf_merge(bm25_dicts, grep_dicts, limit)
        mode = "hybrid"
    else:
        final_results = bm25_dicts[:limit]
        mode = "bm25"

    enriched = []
    for r in final_results:
        page = pages_by_slug.get(r["slug"])
        entry = {"slug": r["slug"], "score": r["score"]}
        if page:
            entry["title"] = page.title
            if page.description:
                entry["description"] = page.description
            entry["tags"] = page.tags
        enriched.append(entry)

    return ExecutionResult(
        data={"mode": mode, "query": query, "count": len(enriched), "results": enriched}
    )
