"""PhilipAdapter — rub adapter aggregating all philip operations.

Supports extension via the ``philip.extensions`` entry-point group.
External packages can register additional operations that are merged
into the philip CLI and the ``rub philip://`` protocol.

Example (in an external package's ``pyproject.toml``)::

    [project.entry-points.'philip.extensions']
    my-feature = "my_pkg.cli:MyExtension"

The entry point must load to a module or object exposing:

- ``OPERATIONS: list[Operation]``
- ``DETAILS: dict[str, OperationDetail]``
- ``_EXECUTE: dict[str, (is_async, execute_fn)]``
"""

from __future__ import annotations

import importlib.metadata
from typing import Any

from loguru import logger
from rub.adapter import Adapter, ExecutionResult
from rub.schema import Operation, OperationDetail

from philip.cli import chat
from philip.cli.finance import (
    _EXECUTE as _FINANCE_EXECUTE,
)
from philip.cli.finance import (
    DETAILS as _FINANCE_DETAILS,
)
from philip.cli.finance import (
    OPERATIONS as _FINANCE_OPS,
)
from philip.cli.wiki import (
    _EXECUTE as _WIKI_EXECUTE,
)
from philip.cli.wiki import (
    DETAILS as _WIKI_DETAILS,
)
from philip.cli.wiki import (
    OPERATIONS as _WIKI_OPS,
)


# ---------------------------------------------------------------------------
# Extension discovery
# ---------------------------------------------------------------------------


def _load_extensions() -> tuple[
    list[Operation], dict[str, OperationDetail], dict[str, tuple[bool, Any]]
]:
    """Scan ``philip.extensions`` entry points and return merged registries."""
    ops: list[Operation] = []
    details: dict[str, OperationDetail] = {}
    dispatch: dict[str, tuple[bool, Any]] = {}

    eps = importlib.metadata.entry_points(group="philip.extensions")
    for ep in eps:
        try:
            ext = ep.load()
        except Exception:
            logger.exception("Failed to load philip extension: %s", ep.name)
            continue

        ext_ops = getattr(ext, "OPERATIONS", None) or []
        ext_details = getattr(ext, "DETAILS", None) or {}
        ext_dispatch = getattr(ext, "_EXECUTE", None) or {}

        if not ext_ops and not ext_details:
            logger.warning(
                "Extension %s has no OPERATIONS or DETAILS, skipping", ep.name
            )
            continue

        ops.extend(ext_ops)
        details.update(ext_details)
        dispatch.update(ext_dispatch)
        logger.info(
            "Loaded philip extension: {} ({} operations)",
            ep.name,
            len(ext_ops),
        )

    return ops, details, dispatch


# ---------------------------------------------------------------------------
# Aggregated declarations
# ---------------------------------------------------------------------------

_ALL_OPERATIONS: list[Operation] = [
    *chat.OPERATIONS,
    *_WIKI_OPS,
    *_FINANCE_OPS,
]

_ALL_DETAILS: dict[str, OperationDetail] = {
    **chat.DETAILS,
    **_WIKI_DETAILS,
    **_FINANCE_DETAILS,
}

# operation_id → (is_async, execute_fn)
_DISPATCH: dict[str, tuple[bool, Any]] = {}
for op in chat.OPERATIONS:
    _DISPATCH[op.operation_id] = (True, chat.execute)
for op_id, fn in _WIKI_EXECUTE.items():
    _DISPATCH[op_id] = (False, fn)
for op_id, fn in _FINANCE_EXECUTE.items():
    _DISPATCH[op_id] = (False, fn)

# Merge extensions
_ext_ops, _ext_details, _ext_dispatch = _load_extensions()
_ALL_OPERATIONS.extend(_ext_ops)
_ALL_DETAILS.update(_ext_details)
_DISPATCH.update(_ext_dispatch)


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class PhilipAdapter(Adapter):
    """Rub adapter for philip — agent-native tooling hub."""

    _priority = 100

    async def protocol_name(self) -> str:
        return "philip"

    async def priority(self) -> int:
        return 100

    async def can_handle(self, url: str) -> bool:
        return url.startswith("philip://")

    async def list_operations(self, url: str) -> list[Operation]:
        return _ALL_OPERATIONS

    async def describe_operation(self, url: str, op_id: str) -> OperationDetail:
        if op_id in _ALL_DETAILS:
            return _ALL_DETAILS[op_id]
        for op in _ALL_OPERATIONS:
            if op.operation_id == op_id:
                return OperationDetail(
                    operation_id=op.operation_id,
                    display_name=op.display_name,
                    description=op.description,
                    parameters=op.parameters,
                )
        from rub.errors import OperationNotFoundError

        raise OperationNotFoundError(f"Operation '{op_id}' not found")

    async def execute(
        self,
        url: str,
        op_id: str,
        args: dict[str, Any],
        *,
        auth_headers: dict[str, str] | None = None,
    ) -> ExecutionResult:
        entry = _DISPATCH.get(op_id)
        if entry is not None:
            is_async, fn = entry
            if is_async:
                return await fn(args)
            return fn(args)

        from rub.errors import OperationNotFoundError

        raise OperationNotFoundError(f"Operation '{op_id}' not found")
