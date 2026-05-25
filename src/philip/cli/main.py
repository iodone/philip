"""Philip CLI — agent-native tooling hub."""

from __future__ import annotations

import click


@click.group()
@click.version_option(package_name="philip", prog_name="philip")
def main() -> None:
    """Philip — agent-native tooling for bub."""


# Import and register subcommands
from philip.cli.commands.chat import chat  # noqa: E402
from philip.cli.commands.serve import serve  # noqa: E402
from philip.cli.commands.wiki import wiki  # noqa: E402

main.add_command(chat)
main.add_command(serve)
main.add_command(wiki)


if __name__ == "__main__":
    main()
