# SPDX-FileCopyrightText: 2026 California Institute of Technology ("Caltech")
# SPDX-License-Identifier: Apache-2.0
# Part of opera-vlm, https://github.com/mgovorcin/opera-vlm.
from __future__ import annotations

from pathlib import Path

import click


@click.command("validate")
@click.argument("golden", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("test", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--rtol", type=float, default=1e-5, show_default=True)
@click.option("--atol", type=float, default=1e-6, show_default=True)
@click.pass_context
def validate_cli(
    ctx: click.Context, golden: Path, test: Path, rtol: float, atol: float
) -> None:
    """Compare a TEST product against a GOLDEN product (exit 1 on failure)."""
    from opera_vlm._log import setup_logging
    from opera_vlm.validate import compare_products

    setup_logging(level="DEBUG" if ctx.obj.get("debug") else "INFO")
    report = compare_products(golden, test, rtol=rtol, atol=atol)
    report.log()
    ctx.exit(0 if report.passed else 1)
