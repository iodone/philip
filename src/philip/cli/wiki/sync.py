"""wiki.sync — Track changes and update sync state."""

from __future__ import annotations

from typing import Any

from rub.adapter import ExecutionResult
from rub.schema import Operation, OperationDetail, Parameter

from philip.capabilities.wiki.config import load_config, require_vault_root, vault_paths
from philip.capabilities.wiki.sync import (
    compute_sync,
    load_sync_state,
    save_sync_state,
    update_sync_state,
)

# ---------------------------------------------------------------------------
# Declarative operation metadata
# ---------------------------------------------------------------------------

OPERATIONS: list[Operation] = [
    Operation(
        operation_id="wiki.sync",
        display_name="Wiki Sync",
        description="Track changes and update sync state (mtime + content hash)",
        parameters=[
            Parameter(
                name="dry_run",
                param_type="boolean",
                default=False,
                description="Show changes without updating state",
            ),
        ],
    ),
]

DETAILS: dict[str, OperationDetail] = {
    "wiki.sync": OperationDetail(
        operation_id="wiki.sync",
        display_name="Wiki Sync",
        description=(
            "Track file changes (added/modified/deleted)"
            " and update sync state. Optionally syncs to DB9."
        ),
        parameters=OPERATIONS[0].parameters,
        return_type="object",
        invocation_examples=[
            "philip wiki.sync",
            "philip wiki.sync dry_run=true",
        ],
    ),
}


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


def execute(args: dict[str, Any]) -> ExecutionResult:
    dry_run = bool(args.get("dry_run", False))

    root = require_vault_root()
    config = load_config(root)
    paths = vault_paths(root, config)
    paths.llm_wiki_dir.mkdir(parents=True, exist_ok=True)

    state = load_sync_state(paths.sync_state)
    result = compute_sync([paths.wiki, paths.contexts], root, state)

    total_changes = len(result.added) + len(result.modified) + len(result.deleted)

    if total_changes == 0:
        return ExecutionResult(data={"changes": 0, "message": "Everything up to date."})

    output: dict[str, Any] = {
        "changes": total_changes,
        "added": result.added,
        "modified": result.modified,
        "deleted": result.deleted,
        "unchanged": len(result.unchanged),
    }

    if dry_run:
        output["dry_run"] = True
        return ExecutionResult(data=output)

    new_state = update_sync_state([paths.wiki, paths.contexts], root, state)
    save_sync_state(paths.sync_state, new_state)
    output["last_sync"] = new_state.last_sync

    # Sync to DB9 if configured
    if config.db9 and config.db9.url:
        from philip.capabilities.wiki.db9 import create_db9_client
        from philip.capabilities.wiki.sync import content_hash as compute_hash
        from philip.capabilities.wiki.wiki import parse_wiki_page

        db9 = create_db9_client(config)
        if db9:
            try:
                db9.ensure_schema()

                wiki_changes = [
                    f for f in (result.added + result.modified) if f.startswith("wiki/")
                ]
                for rel in wiki_changes:
                    file_path = root / rel
                    page = parse_wiki_page(file_path, paths.wiki)
                    h = compute_hash(file_path)
                    db9.upsert_page(page, h)

                wiki_deleted = [f for f in result.deleted if f.startswith("wiki/")]
                for rel in wiki_deleted:
                    slug = rel.removeprefix("wiki/").removesuffix(".md")
                    db9.delete_page(slug)

                output["db9_synced"] = len(wiki_changes) + len(wiki_deleted)
            except Exception as err:
                output["db9_error"] = str(err)
            finally:
                db9.close()

    return ExecutionResult(data=output)
