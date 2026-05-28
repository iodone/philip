"""Philip CLI — rub standalone adapter."""

from rub.standalone import standalone_cli

from philip.cli.adapter import PhilipAdapter

app = standalone_cli(PhilipAdapter(), name="philip", default_url="philip://local")
