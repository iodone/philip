"""wiki.init — Initialize a new wiki workspace."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from rub.adapter import ExecutionResult
from rub.schema import Operation, OperationDetail, Parameter

from philip.capabilities.wiki.config import VaultSection, WikiConfig, vault_paths

# ---------------------------------------------------------------------------
# Declarative operation metadata
# ---------------------------------------------------------------------------

OPERATIONS: list[Operation] = [
    Operation(
        operation_id="wiki.init",
        display_name="Wiki Init",
        description=(
            "Initialize a new wiki workspace with" " vault, rules, contexts, and skills"
        ),
        parameters=[
            Parameter(
                name="directory",
                param_type="string",
                default=".",
                description="Target directory",
            ),
            Parameter(
                name="force",
                param_type="boolean",
                default=False,
                description="Overwrite existing files",
            ),
        ],
    ),
]

DETAILS: dict[str, OperationDetail] = {
    "wiki.init": OperationDetail(
        operation_id="wiki.init",
        display_name="Wiki Init",
        description=(
            "Initialize a new wiki workspace. Creates vault,"
            " rules, contexts, and agent skills."
            " Safe to run multiple times."
        ),
        parameters=OPERATIONS[0].parameters,
        return_type="object",
        invocation_examples=[
            "philip wiki.init",
            "philip wiki.init directory=/path/to/wiki",
            "philip wiki.init force=true",
        ],
    ),
}


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


def execute(args: dict[str, Any]) -> ExecutionResult:
    from philip.capabilities.wiki.config import _TEMPLATES_DIR
    from philip.capabilities.wiki.skills import install_skills_to

    target = Path(args.get("directory", ".")).resolve()
    force = bool(args.get("force", False))

    default_config = WikiConfig(
        vault=VaultSection(
            name="My Wiki", language="en", wiki_dir="wiki", pages_subdir="pages"
        )
    )
    paths = vault_paths(target, default_config)

    dirs_to_create = [
        paths.wiki,
        paths.contexts,
        paths.contexts / "blog",
        paths.contexts / "clippings",
        paths.contexts / "daily_records",
        paths.contexts / "life_record",
        paths.contexts / "survey_sessions",
        paths.contexts / "thought_review",
        paths.llm_wiki_dir,
    ]
    for d in dirs_to_create:
        d.mkdir(parents=True, exist_ok=True)

    created: list[str] = []
    skipped: list[str] = []

    for src_file in sorted(_TEMPLATES_DIR.rglob("*")):
        if not src_file.is_file():
            continue
        rel = src_file.relative_to(_TEMPLATES_DIR)
        dest = paths.config if str(rel) == "config.toml" else target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        rel_str = str(dest.relative_to(target))
        if not dest.exists() or force:
            shutil.copy2(src_file, dest)
            created.append(rel_str)
        else:
            skipped.append(rel_str)

    skill_result = install_skills_to(paths.agents_skills_dir, overwrite=force)
    skill_installed = [
        f".agents/skills/{name}/SKILL.md" for name in skill_result.installed
    ]
    skill_skipped = [f".agents/skills/{name}/SKILL.md" for name in skill_result.skipped]
    if not force:
        created.extend(skill_installed)
        skipped.extend(skill_skipped)
    elif skill_installed:
        created.extend(skill_installed)

    return ExecutionResult(
        data={"target": str(target), "created": created, "skipped": skipped}
    )
