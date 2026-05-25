"""philip serve — standalone debug entry for JSON-RPC server.

This is a convenience debug entry. The production path is `bub gateway`,
which auto-discovers JsonRpcChannel via the provide_channels hookimpl
in PhilipPlugin.

Usage:
  philip serve [--host 127.0.0.1] [--port 8420]
"""

from __future__ import annotations

import click


@click.command("serve")
@click.option("--host", default="127.0.0.1", help="Bind address")
@click.option("--port", default=8420, type=int, help="Bind port")
def serve(host: str, port: int) -> None:
    """Start Philip JSON-RPC server (debug entry).

    Production: use `bub gateway` instead — JsonRpcChannel is
    auto-discovered via PhilipPlugin.provide_channels hookimpl.

    This debug entry wires JsonRpcChannel directly to BubFramework
    for local end-to-end testing.

    Exposes:
      - POST /rpc  — JSON-RPC 2.0 over HTTP
      - GET  /ws   — JSON-RPC 2.0 over WebSocket
    """
    import asyncio
    from typing import Any

    from bub.framework import BubFramework

    from philip.channels.jsonrpc_channel import JsonRpcChannel

    framework = BubFramework()
    framework.load_hooks()

    async def _on_receive(msg: Any) -> None:
        """Adapter: feed inbound message to Bub's process_inbound."""
        await framework.process_inbound(msg)

    click.echo(f"Philip debug serve on http://{host}:{port}")
    click.echo("  (Production: use `bub gateway` — channel auto-discovered)")

    async def _run() -> None:
        stop_event = asyncio.Event()
        channel = JsonRpcChannel(
            on_receive=_on_receive,
            host=host,
            port=port,
        )

        async with framework.running():
            await channel.start(stop_event)
            click.echo("Channel started (framework running)")
            try:
                await stop_event.wait()
            except (KeyboardInterrupt, asyncio.CancelledError):
                pass
            finally:
                await channel.stop()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        click.echo("\nShutting down.")
