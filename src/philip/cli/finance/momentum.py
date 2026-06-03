"""finance.momentum — Tech theme capital rotation monitor."""

from __future__ import annotations

from typing import Any

from rub.adapter import ExecutionResult
from rub.schema import Operation, OperationDetail

from philip.capabilities.finance.tech_rotation import run_rotation_monitor

# ---------------------------------------------------------------------------
# Declarative operation metadata
# ---------------------------------------------------------------------------

OPERATIONS: list[Operation] = [
    Operation(
        operation_id="finance.momentum",
        display_name="Finance Momentum",
        description="Tech theme capital momentum monitor (relative to QQQ)",
        parameters=[],
    ),
]

DETAILS: dict[str, OperationDetail] = {
    "finance.momentum": OperationDetail(
        operation_id="finance.momentum",
        display_name="Finance Momentum",
        description=(
            "Monitor tech theme capital momentum relative to QQQ benchmark."
            " Tracks 11 themes via ETFs and stock baskets."
            " Returns scores, trend codes, and state signals."
        ),
        parameters=[],
        return_type="object",
        invocation_examples=["philip finance.momentum"],
    ),
}


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


def execute(args: dict[str, Any]) -> ExecutionResult:
    results = run_rotation_monitor()
    return ExecutionResult(
        data={
            "benchmark": "QQQ",
            "theme_count": len(results),
            "themes": results,
        }
    )
