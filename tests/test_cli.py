"""Tests for philip CLI — rub standalone adapter."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from philip.cli.__main__ import app

runner = CliRunner()


def _invoke(*args: str):
    return runner.invoke(app, list(args))


def test_cli_discover():
    result = _invoke("-h")
    assert result.exit_code == 0
    assert "wiki.search" in result.output
    assert "wiki.init" in result.output
    assert "chat" in result.output


def test_chat_inspect():
    result = _invoke("chat", "-h")
    assert result.exit_code == 0
    assert "chat" in result.output.lower()


def test_wiki_init(tmp_path: Path):
    target = str(tmp_path / "my-wiki")
    result = _invoke("wiki.init", f"directory={target}")
    assert result.exit_code == 0
    assert (tmp_path / "my-wiki" / "wiki" / "pages").is_dir()
    assert (tmp_path / "my-wiki" / ".llm-wiki" / "config.toml").exists()
    assert (tmp_path / "my-wiki" / "wiki" / "wiki-purpose.md").exists()
    assert (tmp_path / "my-wiki" / "contexts").is_dir()
    assert (tmp_path / "my-wiki" / "contexts" / "clippings").is_dir()
    assert (tmp_path / "my-wiki" / "rules" / "SOUL.md").exists()
    assert (tmp_path / "my-wiki" / "AGENTS.md").exists()
    assert (
        tmp_path / "my-wiki" / ".agents" / "skills" / "workflow-llm-wiki" / "SKILL.md"
    ).exists()


def test_wiki_init_rerun_skips_existing(tmp_path: Path):
    target = str(tmp_path / "my-wiki")
    _invoke("wiki.init", f"directory={target}")

    soul_path = tmp_path / "my-wiki" / "rules" / "SOUL.md"
    soul_path.write_text("Custom SOUL content", encoding="utf-8")

    _invoke("wiki.init", f"directory={target}")
    assert soul_path.read_text(encoding="utf-8") == "Custom SOUL content"


def test_wiki_init_force_overwrites(tmp_path: Path):
    target = str(tmp_path / "my-wiki")
    _invoke("wiki.init", f"directory={target}")

    soul_path = tmp_path / "my-wiki" / "rules" / "SOUL.md"
    soul_path.write_text("Custom SOUL content", encoding="utf-8")

    _invoke("wiki.init", f"directory={target}", "force=true")
    assert soul_path.read_text(encoding="utf-8") != "Custom SOUL content"


def test_wiki_search_outside_vault(tmp_path: Path):
    old_cwd = os.getcwd()
    try:
        os.chdir(str(tmp_path))
        result = _invoke("wiki.search", "query=test")
    finally:
        os.chdir(old_cwd)
    assert result.exit_code != 0 or "No wiki pages" in result.output


def test_wiki_search_in_vault(tmp_path: Path):
    target = str(tmp_path / "my-wiki")
    _invoke("wiki.init", f"directory={target}")

    pages_dir = tmp_path / "my-wiki" / "wiki" / "pages"
    (pages_dir / "test-page.md").write_text(
        "---\ntitle: Test Page\ndescription: A test page\ntags: [test]\n---\n\n"
        "This is about machine learning.\n",
        encoding="utf-8",
    )

    old_cwd = os.getcwd()
    try:
        os.chdir(target)
        result = _invoke("wiki.search", "query=machine learning")
    finally:
        os.chdir(old_cwd)
    assert result.exit_code == 0
    assert "test-page" in result.output


def test_wiki_search_no_results(tmp_path: Path):
    target = str(tmp_path / "my-wiki")
    _invoke("wiki.init", f"directory={target}")

    old_cwd = os.getcwd()
    try:
        os.chdir(target)
        result = _invoke("wiki.search", "query=quantum computing")
    finally:
        os.chdir(old_cwd)
    assert result.exit_code == 0


def test_wiki_status(tmp_path: Path):
    target = str(tmp_path / "my-wiki")
    _invoke("wiki.init", f"directory={target}")

    old_cwd = os.getcwd()
    try:
        os.chdir(target)
        result = _invoke("wiki.status")
    finally:
        os.chdir(old_cwd)
    assert result.exit_code == 0
    assert "wiki" in result.output.lower()


def test_wiki_graph_empty(tmp_path: Path):
    target = str(tmp_path / "my-wiki")
    _invoke("wiki.init", f"directory={target}")

    old_cwd = os.getcwd()
    try:
        os.chdir(target)
        result = _invoke("wiki.graph")
    finally:
        os.chdir(old_cwd)
    assert result.exit_code == 0


def test_wiki_sync(tmp_path: Path):
    target = str(tmp_path / "my-wiki")
    _invoke("wiki.init", f"directory={target}")

    pages_dir = tmp_path / "my-wiki" / "wiki" / "pages"
    (pages_dir / "new-page.md").write_text(
        "---\ntitle: New Page\n---\n\nContent.\n", encoding="utf-8"
    )

    old_cwd = os.getcwd()
    try:
        os.chdir(target)
        result = _invoke("wiki.sync")
    finally:
        os.chdir(old_cwd)
    assert result.exit_code == 0


def test_wiki_sync_dry_run(tmp_path: Path):
    target = str(tmp_path / "my-wiki")
    _invoke("wiki.init", f"directory={target}")

    pages_dir = tmp_path / "my-wiki" / "wiki" / "pages"
    (pages_dir / "new-page.md").write_text(
        "---\ntitle: New Page\n---\n\nContent.\n", encoding="utf-8"
    )

    old_cwd = os.getcwd()
    try:
        os.chdir(target)
        result = _invoke("wiki.sync", "dry_run=true")
    finally:
        os.chdir(old_cwd)
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# DB9 integration tests (mocked psycopg2)
# ---------------------------------------------------------------------------


def test_wiki_search_hybrid_with_db9(tmp_path: Path):
    target = str(tmp_path / "my-wiki")
    _invoke("wiki.init", f"directory={target}")

    config_path = tmp_path / "my-wiki" / ".llm-wiki" / "config.toml"
    config_path.write_text(
        '[vault]\nname = "Test"\nlanguage = "en"\n\n[db9]\nurl = "postgresql://localhost/test"\n',
        encoding="utf-8",
    )

    pages_dir = tmp_path / "my-wiki" / "wiki" / "pages"
    (pages_dir / "test-page.md").write_text(
        "---\ntitle: Test Page\n---\n\nMachine learning content.\n",
        encoding="utf-8",
    )

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchall.return_value = [("test-page", "Test Page", 0.9)]

    with patch("philip.capabilities.wiki.db9._load_psycopg2") as mock_load:
        mock_pg = MagicMock()
        mock_pg.connect.return_value = mock_conn
        mock_load.return_value = mock_pg

        old_cwd = os.getcwd()
        try:
            os.chdir(target)
            result = _invoke("wiki.search", "query=machine learning")
        finally:
            os.chdir(old_cwd)

    assert result.exit_code == 0
    assert "test-page" in result.output


def test_wiki_search_bm25_only_flag(tmp_path: Path):
    target = str(tmp_path / "my-wiki")
    _invoke("wiki.init", f"directory={target}")

    config_path = tmp_path / "my-wiki" / ".llm-wiki" / "config.toml"
    config_path.write_text(
        '[vault]\nname = "Test"\nlanguage = "en"\n\n[db9]\nurl = "postgresql://localhost/test"\n',
        encoding="utf-8",
    )

    pages_dir = tmp_path / "my-wiki" / "wiki" / "pages"
    (pages_dir / "test-page.md").write_text(
        "---\ntitle: Test Page\n---\n\nMachine learning content.\n",
        encoding="utf-8",
    )

    old_cwd = os.getcwd()
    try:
        os.chdir(target)
        result = _invoke("wiki.search", "query=machine learning", "bm25_only=true")
    finally:
        os.chdir(old_cwd)

    assert result.exit_code == 0
    assert "bm25" in result.output.lower()


def test_wiki_sync_with_db9(tmp_path: Path):
    target = str(tmp_path / "my-wiki")
    _invoke("wiki.init", f"directory={target}")

    config_path = tmp_path / "my-wiki" / ".llm-wiki" / "config.toml"
    config_path.write_text(
        '[vault]\nname = "Test"\nlanguage = "en"\n\n[db9]\nurl = "postgresql://localhost/test"\n',
        encoding="utf-8",
    )

    pages_dir = tmp_path / "my-wiki" / "wiki" / "pages"
    (pages_dir / "test-page.md").write_text(
        "---\ntitle: Test Page\n---\n\nContent.\n", encoding="utf-8"
    )

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    with patch("philip.capabilities.wiki.db9._load_psycopg2") as mock_load:
        mock_pg = MagicMock()
        mock_pg.connect.return_value = mock_conn
        mock_load.return_value = mock_pg

        old_cwd = os.getcwd()
        try:
            os.chdir(target)
            result = _invoke("wiki.sync")
        finally:
            os.chdir(old_cwd)

    assert result.exit_code == 0


def test_wiki_sync_db9_dry_run_no_upsert(tmp_path: Path):
    target = str(tmp_path / "my-wiki")
    _invoke("wiki.init", f"directory={target}")

    config_path = tmp_path / "my-wiki" / ".llm-wiki" / "config.toml"
    config_path.write_text(
        '[vault]\nname = "Test"\nlanguage = "en"\n\n[db9]\nurl = "postgresql://localhost/test"\n',
        encoding="utf-8",
    )

    pages_dir = tmp_path / "my-wiki" / "wiki" / "pages"
    (pages_dir / "test-page.md").write_text(
        "---\ntitle: Test Page\n---\n\nContent.\n", encoding="utf-8"
    )

    old_cwd = os.getcwd()
    try:
        os.chdir(target)
        result = _invoke("wiki.sync", "dry_run=true")
    finally:
        os.chdir(old_cwd)

    assert result.exit_code == 0
    assert "db9_synced" not in result.output
