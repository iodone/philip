"""Tests for philip finance CLI — tech momentum monitor."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from philip.cli.__main__ import app

runner = CliRunner()


def _invoke(*args: str):
    return runner.invoke(app, list(args))


# ─── CLI Registration ────────────────────────────────────────────


def test_finance_momentum_discover():
    result = _invoke("-h")
    assert result.exit_code == 0
    assert "finance.momentum" in result.output


def test_finance_momentum_inspect():
    result = _invoke("finance.momentum", "-h")
    assert result.exit_code == 0
    assert "momentum" in result.output.lower()


# ─── Execution ───────────────────────────────────────────────────


def test_finance_momentum_execute():
    mock_results = [
        {
            "valid": True,
            "theme": "AI综合",
            "proxy": "AIQ",
            "rel1": 0.5,
            "rel5": 1.2,
            "rel20": 3.4,
            "rel60": 8.0,
            "vol_ratio": 1.5,
            "breadth": 75.0,
            "score": 80,
            "trend_code": 2,
            "state": 2,
        },
        {
            "valid": True,
            "theme": "半导体",
            "proxy": "SMH",
            "rel1": -0.3,
            "rel5": -0.8,
            "rel20": 1.0,
            "rel60": 5.0,
            "vol_ratio": 0.9,
            "breadth": 50.0,
            "score": 55,
            "trend_code": 1,
            "state": 0,
        },
    ]

    with patch(
        "philip.cli.finance.momentum.run_rotation_monitor",
        return_value=mock_results,
    ):
        result = _invoke("finance.momentum")

    assert result.exit_code == 0
    assert "finance" in result.output.lower() or "momentum" in result.output.lower()


def test_finance_momentum_empty():
    with patch(
        "philip.cli.finance.momentum.run_rotation_monitor",
        return_value=[],
    ):
        result = _invoke("finance.momentum")

    assert result.exit_code == 0
