"""Philip wiki commands — wraps llm-wiki CLI."""

from __future__ import annotations

import shutil
import subprocess
import sys

import click


def _find_llm_wiki() -> str:
    """Locate the llm-wiki binary, or exit with a helpful message."""
    path = shutil.which("llm-wiki")
    if path is None:
        click.echo(
            "Error: llm-wiki not found on PATH.\n"
            "Install: npm install -g @iodone/llm-wiki\n"
            "Or:      git clone https://github.com/iodone/llm-wiki && cd llm-wiki "
            "&& npm install && npm run build && npm link",
            err=True,
        )
        raise SystemExit(1)
    return path


def _run(args: list[str], *, cwd: str | None = None) -> int:
    """Run an llm-wiki subcommand, streaming output."""
    cmd = [_find_llm_wiki(), *args]
    result = subprocess.run(cmd, cwd=cwd)  # noqa: S603
    return result.returncode


@click.group()
def wiki() -> None:
    """Wiki vault operations (wraps llm-wiki)."""


@wiki.command()
@click.argument("directory", default=".")
def init(directory: str) -> None:
    """Initialize a new wiki vault."""
    raise SystemExit(_run(["init", directory]))


@wiki.command()
@click.argument("query")
@click.option("-n", "--limit", default=10, help="Max results.")
@click.option("--bm25-only", is_flag=True, help="Force BM25-only search.")
def search(query: str, limit: int, bm25_only: bool) -> None:
    """Search wiki pages (BM25 + vector)."""
    args: list[str] = ["search", "-n", str(limit)]
    if bm25_only:
        args.append("--bm25-only")
    args.append(query)
    raise SystemExit(_run(args))


@wiki.command()
@click.option("--dry-run", is_flag=True, help="Show changes without updating state.")
def sync(dry_run: bool) -> None:
    """Update search index and sync state."""
    args: list[str] = ["sync"]
    if dry_run:
        args.append("--dry-run")
    raise SystemExit(_run(args))


@wiki.command()
def status() -> None:
    """Show wiki statistics and health summary."""
    raise SystemExit(_run(["status"]))


@wiki.command()
@click.option("--json", "output_json", is_flag=True, help="Output as JSON.")
def graph(output_json: bool) -> None:
    """Analyze wiki link graph — communities, hubs, orphans, wanted pages."""
    args: list[str] = ["graph"]
    if output_json:
        args.append("--json")
    raise SystemExit(_run(args))
