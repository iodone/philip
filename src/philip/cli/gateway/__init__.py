"""Gateway operations — aggregated from sub-modules."""

from __future__ import annotations

from typing import Any

from rub.schema import Operation, OperationDetail

from philip.cli.gateway import start

_MODULES = [start]

OPERATIONS: list[Operation] = [op for m in _MODULES for op in m.OPERATIONS]
DETAILS: dict[str, OperationDetail] = {}
for m in _MODULES:
    DETAILS.update(m.DETAILS)
_EXECUTE: dict[str, Any] = {}
for m in _MODULES:
    for op in m.OPERATIONS:
        _EXECUTE[op.operation_id] = m.execute
