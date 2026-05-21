"""Tests for philip CLI — wiki commands now use internal Python implementation."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from philip.cli.main import main


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "philip" in result.output.lower()


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "wiki" in result.output


def test_wiki_help():
    runner = CliRunner()
    result = runner.invoke(main, ["wiki", "--help"])
    assert result.exit_code == 0
    assert "search" in result.output
    assert "init" in result.output
    assert "sync" in result.output
    assert "status" in result.output
    assert "graph" in result.output


def test_wiki_init(tmp_path: Path):
    """Test vault initialization creates expected structure."""
    runner = CliRunner()
    target = str(tmp_path / "my-wiki")
    result = runner.invoke(main, ["wiki", "init", target])
    assert result.exit_code == 0
    assert "Initialized" in result.output
    # Wiki
    assert (tmp_path / "my-wiki" / "wiki" / "pages").is_dir()
    assert (tmp_path / "my-wiki" / ".llm-wiki" / "config.toml").exists()
    assert (tmp_path / "my-wiki" / "wiki" / "wiki-purpose.md").exists()
    # Contexts
    assert (tmp_path / "my-wiki" / "contexts").is_dir()
    assert (tmp_path / "my-wiki" / "contexts" / "clippings").is_dir()
    assert (tmp_path / "my-wiki" / "contexts" / "survey_sessions").is_dir()
    # Rules
    assert (tmp_path / "my-wiki" / "rules" / "SOUL.md").exists()
    assert (tmp_path / "my-wiki" / "rules" / "WORKSPACE.md").exists()
    # Workspace files
    assert (tmp_path / "my-wiki" / "AGENTS.md").exists()
    assert (tmp_path / "my-wiki" / "README.md").exists()
    # Skills auto-installed
    assert (tmp_path / "my-wiki" / ".agents" / "skills" / "workflow-llm-wiki" / "SKILL.md").exists()
    assert "skill" in result.output.lower() or "SKILL.md" in result.output


def test_wiki_init_rerun_skips_existing(tmp_path: Path):
    """Test that re-running init skips existing files."""
    runner = CliRunner()
    target = str(tmp_path / "my-wiki")

    # First run
    runner.invoke(main, ["wiki", "init", target])

    # Modify a file
    soul_path = tmp_path / "my-wiki" / "rules" / "SOUL.md"
    original_content = soul_path.read_text(encoding="utf-8")
    soul_path.write_text("Custom SOUL content", encoding="utf-8")

    # Second run — should skip existing
    result = runner.invoke(main, ["wiki", "init", target])
    assert result.exit_code == 0
    assert "Skipped" in result.output
    # File should NOT be overwritten
    assert soul_path.read_text(encoding="utf-8") == "Custom SOUL content"


def test_wiki_init_skill_skip(tmp_path: Path):
    """Test that re-running init skips existing skill files."""
    runner = CliRunner()
    target = str(tmp_path / "my-wiki")

    # First run installs skill
    runner.invoke(main, ["wiki", "init", target])
    skill_path = tmp_path / "my-wiki" / ".agents" / "skills" / "workflow-llm-wiki" / "SKILL.md"
    assert skill_path.exists()
    skill_path.write_text("Custom skill content", encoding="utf-8")

    # Second run without --force should NOT overwrite skill
    runner.invoke(main, ["wiki", "init", target])
    assert skill_path.read_text(encoding="utf-8") == "Custom skill content"

    # Third run with --force should overwrite skill
    runner.invoke(main, ["wiki", "init", "--force", target])
    assert skill_path.read_text(encoding="utf-8") != "Custom skill content"


def test_wiki_init_force_overwrites(tmp_path: Path):
    """Test that --force overwrites existing files."""
    runner = CliRunner()
    target = str(tmp_path / "my-wiki")

    # First run
    runner.invoke(main, ["wiki", "init", target])

    # Modify a file
    soul_path = tmp_path / "my-wiki" / "rules" / "SOUL.md"
    soul_path.write_text("Custom SOUL content", encoding="utf-8")

    # Second run with --force
    result = runner.invoke(main, ["wiki", "init", "--force", target])
    assert result.exit_code == 0
    # File should be overwritten with template
    assert soul_path.read_text(encoding="utf-8") != "Custom SOUL content"


def test_wiki_search_outside_vault(tmp_path: Path):
    """Search outside a vault should fail gracefully."""
    runner = CliRunner()
    old_cwd = os.getcwd()
    try:
        os.chdir(str(tmp_path))
        result = runner.invoke(main, ["wiki", "search", "test"])
    finally:
        os.chdir(old_cwd)
    assert result.exit_code != 0


def test_wiki_search_in_vault(tmp_path: Path):
    """Search inside a vault with pages."""
    runner = CliRunner()

    # Initialize vault
    target = str(tmp_path / "my-wiki")
    runner.invoke(main, ["wiki", "init", target])

    # Add a wiki page
    pages_dir = tmp_path / "my-wiki" / "wiki" / "pages"
    (pages_dir / "test-page.md").write_text(
        "---\ntitle: Test Page\ndescription: A test page\ntags: [test]\n---\n\nThis is about machine learning.\n",
        encoding="utf-8",
    )

    old_cwd = os.getcwd()
    try:
        os.chdir(target)
        result = runner.invoke(main, ["wiki", "search", "machine learning"])
    finally:
        os.chdir(old_cwd)
    assert result.exit_code == 0
    assert "test-page" in result.output


def test_wiki_search_no_results(tmp_path: Path):
    """Search with no matching pages."""
    runner = CliRunner()

    target = str(tmp_path / "my-wiki")
    runner.invoke(main, ["wiki", "init", target])

    old_cwd = os.getcwd()
    try:
        os.chdir(target)
        result = runner.invoke(main, ["wiki", "search", "quantum computing"])
    finally:
        os.chdir(old_cwd)
    assert result.exit_code == 0
    assert "No wiki pages" in result.output or "No results" in result.output


def test_wiki_status(tmp_path: Path):
    """Status command in a vault."""
    runner = CliRunner()

    target = str(tmp_path / "my-wiki")
    runner.invoke(main, ["wiki", "init", target])

    old_cwd = os.getcwd()
    try:
        os.chdir(target)
        result = runner.invoke(main, ["wiki", "status"])
    finally:
        os.chdir(old_cwd)
    assert result.exit_code == 0
    assert "Wiki:" in result.output
    assert "Pages:" in result.output
    assert "Contexts:" in result.output


def test_wiki_graph_empty(tmp_path: Path):
    """Graph command with no pages."""
    runner = CliRunner()

    target = str(tmp_path / "my-wiki")
    runner.invoke(main, ["wiki", "init", target])

    old_cwd = os.getcwd()
    try:
        os.chdir(target)
        result = runner.invoke(main, ["wiki", "graph"])
    finally:
        os.chdir(old_cwd)
    assert result.exit_code == 0
    assert "No wiki pages" in result.output


def test_wiki_sync(tmp_path: Path):
    """Sync command tracks changes."""
    runner = CliRunner()

    target = str(tmp_path / "my-wiki")
    runner.invoke(main, ["wiki", "init", target])

    # Add a page
    pages_dir = tmp_path / "my-wiki" / "wiki" / "pages"
    (pages_dir / "new-page.md").write_text(
        "---\ntitle: New Page\n---\n\nContent.\n",
        encoding="utf-8",
    )

    old_cwd = os.getcwd()
    try:
        os.chdir(target)
        result = runner.invoke(main, ["wiki", "sync"])
    finally:
        os.chdir(old_cwd)
    assert result.exit_code == 0
    assert "Added" in result.output or "changes" in result.output


def test_wiki_sync_dry_run(tmp_path: Path):
    """Sync --dry-run shows changes without updating state."""
    runner = CliRunner()

    target = str(tmp_path / "my-wiki")
    runner.invoke(main, ["wiki", "init", target])

    pages_dir = tmp_path / "my-wiki" / "wiki" / "pages"
    (pages_dir / "new-page.md").write_text(
        "---\ntitle: New Page\n---\n\nContent.\n",
        encoding="utf-8",
    )

    old_cwd = os.getcwd()
    try:
        os.chdir(target)
        result = runner.invoke(main, ["wiki", "sync", "--dry-run"])
    finally:
        os.chdir(old_cwd)
    assert result.exit_code == 0
    assert "dry run" in result.output


def test_wiki_skill_list():
    """Skill list shows available skills."""
    runner = CliRunner()
    result = runner.invoke(main, ["wiki", "skill"])
    assert result.exit_code == 0
    assert "workflow-llm-wiki" in result.output


def test_wiki_skill_install(tmp_path: Path):
    """Skill install copies SKILL.md to target."""
    runner = CliRunner()
    result = runner.invoke(main, ["wiki", "skill", "install", "--dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "Installed" in result.output
    assert (tmp_path / ".claude" / "skills" / "workflow-llm-wiki" / "SKILL.md").exists()
    assert (tmp_path / ".agents" / "skills" / "workflow-llm-wiki" / "SKILL.md").exists()


# ---------------------------------------------------------------------------
# DB9 integration tests (mocked psycopg2)
# ---------------------------------------------------------------------------


def test_wiki_search_hybrid_with_db9(tmp_path: Path):
    """Search with DB9 configured produces hybrid results."""
    import json

    runner = CliRunner()

    # Initialize vault
    target = str(tmp_path / "my-wiki")
    runner.invoke(main, ["wiki", "init", target])

    # Add DB9 config
    config_path = tmp_path / "my-wiki" / ".llm-wiki" / "config.toml"
    config_path.write_text(
        '[vault]\nname = "Test"\nlanguage = "en"\n\n[db9]\nurl = "postgresql://localhost/test"\n',
        encoding="utf-8",
    )

    # Add a wiki page
    pages_dir = tmp_path / "my-wiki" / "wiki" / "pages"
    (pages_dir / "test-page.md").write_text(
        "---\ntitle: Test Page\n---\n\nMachine learning content.\n",
        encoding="utf-8",
    )

    # Mock psycopg2 for DB9 vector search
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchall.return_value = [
        ("test-page", "Test Page", 0.9),
    ]

    with patch("philip.wiki.db9._load_psycopg2") as mock_load:
        mock_pg = MagicMock()
        mock_pg.connect.return_value = mock_conn
        mock_load.return_value = mock_pg

        old_cwd = os.getcwd()
        try:
            os.chdir(target)
            result = runner.invoke(main, ["wiki", "search", "machine learning"])
        finally:
            os.chdir(old_cwd)

    assert result.exit_code == 0
    # Should show hybrid mode since DB9 is configured and returns results
    assert "hybrid" in result.output.lower() or "test-page" in result.output


def test_wiki_search_bm25_only_flag(tmp_path: Path):
    """--bm25-only skips DB9 even when configured."""
    runner = CliRunner()

    target = str(tmp_path / "my-wiki")
    runner.invoke(main, ["wiki", "init", target])

    # Add DB9 config
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
        result = runner.invoke(main, ["wiki", "search", "--bm25-only", "machine learning"])
    finally:
        os.chdir(old_cwd)

    assert result.exit_code == 0
    assert "BM25" in result.output
    assert "hybrid" not in result.output.lower()


def test_wiki_sync_with_db9(tmp_path: Path):
    """Sync with DB9 configured performs upsert/delete."""
    runner = CliRunner()

    target = str(tmp_path / "my-wiki")
    runner.invoke(main, ["wiki", "init", target])

    # Add DB9 config
    config_path = tmp_path / "my-wiki" / ".llm-wiki" / "config.toml"
    config_path.write_text(
        '[vault]\nname = "Test"\nlanguage = "en"\n\n[db9]\nurl = "postgresql://localhost/test"\n',
        encoding="utf-8",
    )

    # Add a wiki page
    pages_dir = tmp_path / "my-wiki" / "wiki" / "pages"
    (pages_dir / "test-page.md").write_text(
        "---\ntitle: Test Page\n---\n\nContent.\n",
        encoding="utf-8",
    )

    # Mock psycopg2
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    with patch("philip.wiki.db9._load_psycopg2") as mock_load:
        mock_pg = MagicMock()
        mock_pg.connect.return_value = mock_conn
        mock_load.return_value = mock_pg

        old_cwd = os.getcwd()
        try:
            os.chdir(target)
            result = runner.invoke(main, ["wiki", "sync"])
        finally:
            os.chdir(old_cwd)

    assert result.exit_code == 0
    assert "DB9 sync complete" in result.output
    # Should have attempted to upsert the wiki page
    assert any("INSERT INTO wiki_index" in str(c) for c in mock_cursor.execute.call_args_list)
    assert any("wiki_page_contexts" in str(c) for c in mock_cursor.execute.call_args_list)


def test_wiki_sync_db9_dry_run_no_upsert(tmp_path: Path):
    """Sync --dry-run with DB9 skips upsert."""
    runner = CliRunner()

    target = str(tmp_path / "my-wiki")
    runner.invoke(main, ["wiki", "init", target])

    config_path = tmp_path / "my-wiki" / ".llm-wiki" / "config.toml"
    config_path.write_text(
        '[vault]\nname = "Test"\nlanguage = "en"\n\n[db9]\nurl = "postgresql://localhost/test"\n',
        encoding="utf-8",
    )

    pages_dir = tmp_path / "my-wiki" / "wiki" / "pages"
    (pages_dir / "test-page.md").write_text(
        "---\ntitle: Test Page\n---\n\nContent.\n",
        encoding="utf-8",
    )

    old_cwd = os.getcwd()
    try:
        os.chdir(target)
        result = runner.invoke(main, ["wiki", "sync", "--dry-run"])
    finally:
        os.chdir(old_cwd)

    assert result.exit_code == 0
    assert "dry run" in result.output
    # Should NOT show DB9 sync (dry run exits before DB9 operations)
    assert "DB9 sync" not in result.output
