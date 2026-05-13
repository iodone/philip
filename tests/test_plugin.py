"""Tests for Philip's Bub plugin registration."""

from __future__ import annotations

from importlib import metadata


def test_philip_registers_bub_plugin_entry_point():
    entry_points = metadata.entry_points(group="bub")
    assert any(ep.name == "philip" for ep in entry_points)
