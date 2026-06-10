"""wiki.search — Block-level search with structured input support."""

from __future__ import annotations

import json
from typing import Any

from rub.adapter import ExecutionResult
from rub.errors import InvalidArgumentsError
from rub.schema import Operation, OperationDetail, Parameter

from philip.capabilities.wiki.config import load_config, require_vault_root, vault_paths
from philip.capabilities.wiki.search import Block, parse_blocks, tiered_rank
from philip.capabilities.wiki.wiki import load_wiki_pages

# ---------------------------------------------------------------------------
# Declarative operation metadata
# ---------------------------------------------------------------------------

OPERATIONS: list[Operation] = [
    Operation(
        operation_id="wiki.search",
        display_name="Wiki Search",
        description="Block-level search with BM25 + ripgrep tiered ranking",
        parameters=[
            Parameter(
                name="query",
                param_type="string",
                required=False,
                description="Plain text query (backward compatible)",
            ),
            Parameter(
                name="exact_terms",
                param_type="string",
                required=False,
                description='JSON array of exact terms, e.g. \'["Falcon", "Doris"]\'',
            ),
            Parameter(
                name="fuzzy_terms",
                param_type="string",
                required=False,
                description='JSON array of fuzzy terms, e.g. \'["慢查询", "报警"]\'',
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
        description=(
            "Block-level wiki search. Splits pages by Markdown headers,"
            " uses BM25 for semantic recall + ripgrep for exact matching,"
            " with tiered ranking (exact hits get VIP priority)."
            " Supports both plain query and structured exact_terms/fuzzy_terms."
        ),
        parameters=OPERATIONS[0].parameters,
        return_type="object",
        invocation_examples=[
            "philip wiki.search query=agent",
            'philip wiki.search exact_terms=\'["Falcon"]\' fuzzy_terms=\'["慢查询","报警","alert"]\'',
            'philip wiki.search exact_terms=\'["BM25","ripgrep"]\'',
            'philip wiki.search fuzzy_terms=\'["知识库","编译","索引"]\'',
            "philip wiki.search query=architecture limit=5",
        ],
    ),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_json_array(raw: str | None) -> list[str]:
    """Parse a JSON array string, return empty list on failure."""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
    except (json.JSONDecodeError, TypeError):
        pass
    return []


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


def execute(args: dict[str, Any]) -> ExecutionResult:
    query = args.get("query", "")
    exact_terms = _parse_json_array(args.get("exact_terms"))
    fuzzy_terms = _parse_json_array(args.get("fuzzy_terms"))
    limit = int(args.get("limit", 10))

    # Backward compatible: plain query → treat as both exact and fuzzy
    if query and not exact_terms and not fuzzy_terms:
        exact_terms = [query]
        fuzzy_terms = [query]

    if not exact_terms and not fuzzy_terms:
        raise InvalidArgumentsError(
            "Provide either query or exact_terms/fuzzy_terms"
        )

    root = require_vault_root()
    config = load_config(root)
    paths = vault_paths(root, config)
    pages = load_wiki_pages(paths.wiki)

    if not pages:
        return ExecutionResult(
            data={"mode": "none", "snippets": [], "message": "No wiki pages found."}
        )

    # Parse all pages into blocks
    wiki_dir = str(paths.wiki)
    blocks: list[Block] = []
    for page in pages:
        content = page.content
        if page.title:
            # Prepend title as H1 if not already present
            if not content.lstrip().startswith("# "):
                content = f"# {page.title}\n\n{content}"
        blocks.extend(parse_blocks(str(page.path), content, wiki_dir))

    # Tiered search
    results = tiered_rank(blocks, exact_terms, fuzzy_terms, wiki_dir, limit)

    # Context assembly
    snippets = []
    for r in results:
        snippets.append({
            "source": r.block.file_path,
            "section": r.block.header or "(top)",
            "lines": [r.block.line_start, r.block.line_end],
            "type": r.match_type,
            "content": r.block.content.strip(),
        })

    return ExecutionResult(
        data={
            "mode": "tiered",
            "exact_terms": exact_terms,
            "fuzzy_terms": fuzzy_terms,
            "count": len(snippets),
            "snippets": snippets,
        }
    )
