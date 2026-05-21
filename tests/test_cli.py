"""Tests for philip CLI."""

from __future__ import annotations

from unittest.mock import patch

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


@patch("philip.cli.commands.wiki._find_llm_wiki", return_value="/usr/bin/llm-wiki")
@patch("philip.cli.commands.wiki.subprocess.run")
def test_wiki_search(mock_run, mock_find):
    mock_run.return_value.returncode = 0
    runner = CliRunner()
    result = runner.invoke(main, ["wiki", "search", "test query"])
    assert result.exit_code == 0
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert args[0] == "/usr/bin/llm-wiki"
    assert "search" in args
    assert "test query" in args


@patch("philip.cli.commands.wiki._find_llm_wiki", return_value="/usr/bin/llm-wiki")
@patch("philip.cli.commands.wiki.subprocess.run")
def test_wiki_search_with_limit(mock_run, mock_find):
    mock_run.return_value.returncode = 0
    runner = CliRunner()
    result = runner.invoke(main, ["wiki", "search", "-n", "5", "query"])
    assert result.exit_code == 0
    args = mock_run.call_args[0][0]
    assert "-n" in args
    assert "5" in args


@patch("philip.cli.commands.wiki._find_llm_wiki", return_value="/usr/bin/llm-wiki")
@patch("philip.cli.commands.wiki.subprocess.run")
def test_wiki_sync(mock_run, mock_find):
    mock_run.return_value.returncode = 0
    runner = CliRunner()
    result = runner.invoke(main, ["wiki", "sync"])
    assert result.exit_code == 0
    args = mock_run.call_args[0][0]
    assert "sync" in args


@patch("philip.cli.commands.wiki._find_llm_wiki", return_value="/usr/bin/llm-wiki")
@patch("philip.cli.commands.wiki.subprocess.run")
def test_wiki_status(mock_run, mock_find):
    mock_run.return_value.returncode = 0
    runner = CliRunner()
    result = runner.invoke(main, ["wiki", "status"])
    assert result.exit_code == 0
    args = mock_run.call_args[0][0]
    assert "status" in args


@patch("philip.cli.commands.wiki.shutil.which", return_value=None)
def test_wiki_missing_binary(mock_which):
    runner = CliRunner()
    result = runner.invoke(main, ["wiki", "search", "test"])
    assert result.exit_code != 0
