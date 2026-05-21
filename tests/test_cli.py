"""Tests for philip CLI — wiki commands now use internal Python implementation."""

from __future__ import annotations

import os
from pathlib import Path

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
    assert (tmp_path / "my-wiki" / "wiki" / "pages").is_dir()
    assert (tmp_path / "my-wiki" / ".llm-wiki" / "config.toml").exists()
    assert (tmp_path / "my-wiki" / "wiki" / "wiki-purpose.md").exists()


def test_wiki_init_rejects_existing_vault(tmp_path: Path):
    """Test that init fails inside an existing vault."""
    runner = CliRunner()
    target = str(tmp_path / "my-wiki")
    runner.invoke(main, ["wiki", "init", target])
    result = runner.invoke(main, ["wiki", "init", target])
    assert result.exit_code != 0
    assert "already inside" in result.output


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
    assert "llm-wiki" in result.output


def test_wiki_skill_install(tmp_path: Path):
    """Skill install copies SKILL.md to target."""
    runner = CliRunner()
    result = runner.invoke(main, ["wiki", "skill", "install", "--dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "Installed" in result.output
    assert (tmp_path / ".claude" / "skills" / "llm-wiki" / "SKILL.md").exists()
    assert (tmp_path / ".agents" / "skills" / "llm-wiki" / "SKILL.md").exists()
