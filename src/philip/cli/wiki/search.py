"""wiki.search — Search wiki pages (BM25 + vector)."""

from __future__ import annotations

from typing import Any

from rub.adapter import ExecutionResult
from rub.errors import InvalidArgumentsError
from rub.schema import Operation, OperationDetail, Parameter

from philip.capabilities.wiki.config import load_config, require_vault_root, vault_paths
from philip.capabilities.wiki.search import bm25_search, rrf_merge
from philip.capabilities.wiki.wiki import load_wiki_pages

# ---------------------------------------------------------------------------
# Declarative operation metadata
# ---------------------------------------------------------------------------

OPERATIONS: list[Operation] = [
    Operation(
        operation_id="wiki.search",
        display_name="Wiki Search",
        description="Search wiki pages (BM25 + vector search if configured)",
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
            Parameter(
                name="bm25_only",
                param_type="boolean",
                default=False,
                description="Force BM25-only search",
            ),
        ],
    ),
]

DETAILS: dict[str, OperationDetail] = {
    "wiki.search": OperationDetail(
        operation_id="wiki.search",
        display_name="Wiki Search",
        description=(
            "Search wiki pages using BM25" " (and vector search if DB9 is configured)."
        ),
        parameters=OPERATIONS[0].parameters,
        return_type="object",
        invocation_examples=[
            "philip wiki.search query=machine learning",
            "philip wiki.search query=test limit=5",
            "philip wiki.search query=test bm25_only=true",
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
    bm25_only = bool(args.get("bm25_only", False))

    root = require_vault_root()
    config = load_config(root)
    paths = vault_paths(root, config)
    pages = load_wiki_pages(paths.wiki)

    if not pages:
        return ExecutionResult(
            data={"mode": "none", "results": [], "message": "No wiki pages found."}
        )

    pages_by_slug = {p.slug: p for p in pages}
    bm25_results = bm25_search(pages, query, limit * 2)

    vector_results: list[dict[str, float]] = []
    hybrid_mode = False

    if not bm25_only and config.db9 and config.db9.url:
        try:
            from philip.capabilities.wiki.db9 import create_db9_client

            db9 = create_db9_client(config)
            if db9:
                db_results = db9.vector_search(query, limit * 2)
                vector_results = [
                    {"slug": r["slug"], "score": r["similarity"]} for r in db_results
                ]
                hybrid_mode = len(vector_results) > 0
                db9.close()
        except Exception:
            pass

    if hybrid_mode:
        final_results = rrf_merge(
            [{"slug": r.page.slug, "score": r.score} for r in bm25_results],
            vector_results,
            limit,
        )
        mode = "hybrid"
    else:
        final_results = [
            {"slug": r.page.slug, "score": r.score} for r in bm25_results[:limit]
        ]
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
