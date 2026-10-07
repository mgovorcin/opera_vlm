# SPDX-FileCopyrightText: 2026 California Institute of Technology ("Caltech")
# SPDX-License-Identifier: Apache-2.0
# Part of opera-vlm, https://github.com/mgovorcin/opera-vlm.
from __future__ import annotations

import click

from opera_vlm._version import __version__

from .ceos import ceos_group
from .config import config_group
from .run import run_cli
from .stage import stage_group
from .validate import validate_cli


@click.group(name="opera-vlm")
@click.version_option(version=__version__, prog_name="opera-vlm")
@click.option("--debug", is_flag=True, help="Enable debug logging.")
@click.pass_context
def cli_app(ctx: click.Context, debug: bool) -> None:
    """OPERA Vertical Land Motion from DISP and DISP-CAL."""
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug


cli_app.add_command(run_cli)
cli_app.add_command(config_group)
cli_app.add_command(validate_cli)
cli_app.add_command(ceos_group)
cli_app.add_command(stage_group)


if __name__ == "__main__":
    cli_app()
