"""philip rpc — JSON-RPC client and server commands."""

from __future__ import annotations

import click


@click.group("rpc")
def rpc() -> None:
    """JSON-RPC client and server commands."""
