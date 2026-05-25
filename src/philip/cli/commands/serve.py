"""philip serve — start the JSON-RPC server."""

from __future__ import annotations

import click

from bub.framework import BubFramework

from philip.server.service import Service
from philip.server.session_store import SessionStore


@click.command("serve")
@click.option("--host", default="127.0.0.1", help="Bind address")
@click.option("--port", default=8420, type=int, help="Bind port")
def serve(host: str, port: int) -> None:
    """Start Philip JSON-RPC server.

    Exposes:
      - POST /rpc  — JSON-RPC 2.0 over HTTP
      - GET  /ws   — JSON-RPC 2.0 over WebSocket
    """
    import asyncio

    from aiohttp import web

    from philip.server.transport_http import create_app
    from philip.server.transport_ws import register_ws_route

    framework = BubFramework()
    framework.load_hooks()
    store = SessionStore()
    service = Service(store, framework)
    app = create_app(service)
    register_ws_route(app, service)

    click.echo(f"Philip serve listening on http://{host}:{port}")
    click.echo(f"  POST http://{host}:{port}/rpc")
    click.echo(f"  WS   ws://{host}:{port}/ws")

    async def _run() -> None:
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        async with framework.running():
            await site.start()
            click.echo("Server started (framework running)")
            # Keep running until interrupted
            try:
                await asyncio.Event().wait()
            except (KeyboardInterrupt, asyncio.CancelledError):
                pass
            finally:
                await runner.cleanup()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        click.echo("\nShutting down.")
