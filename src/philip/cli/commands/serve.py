"""philip serve — start the JSON-RPC server."""

from __future__ import annotations

import asyncio

import click

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
    from aiohttp import web

    from philip.server.transport_http import create_app
    from philip.server.transport_ws import register_ws_route

    store = SessionStore()
    service = Service(store)
    app = create_app(service)
    register_ws_route(app, service)

    click.echo(f"Philip serve listening on http://{host}:{port}")
    click.echo(f"  POST http://{host}:{port}/rpc")
    click.echo(f"  WS   ws://{host}:{port}/ws")
    web.run_app(app, host=host, port=port, print=None)
