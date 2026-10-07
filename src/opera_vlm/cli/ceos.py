# SPDX-FileCopyrightText: 2026 California Institute of Technology ("Caltech")
# SPDX-License-Identifier: Apache-2.0
# Part of opera-vlm, https://github.com/mgovorcin/opera-vlm.
"""``opera-vlm ceos``: CEOS-ARD compliance of products and of the declaration."""

from __future__ import annotations

from pathlib import Path

import click


@click.group(name="ceos")
def ceos_group() -> None:
    """CEOS Analysis Ready Data compliance."""


@ceos_group.command("check")
@click.argument("product", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.pass_context
def check_cli(ctx: click.Context, product: Path) -> None:
    """Report every declared CEOS field of PRODUCT; exit 1 unless all required are ok."""
    from opera_vlm.product._ceos import CEOS_ENABLED, check_compliance, is_compliant

    if not CEOS_ENABLED:
        click.echo("This product does not claim CEOS-ARD compliance.")
        return
    report = check_compliance(product)
    for f, status in report:
        flag = "" if f.required else " (optional)"
        click.echo(f"{status:<11} {f.section:<7} {f.group}/{f.name}{flag}")
    ok = is_compliant(report)
    click.echo("CEOS-ARD: " + ("COMPLIANT" if ok else "NOT COMPLIANT"))
    ctx.exit(0 if ok else 1)


@ceos_group.command("matrix")
@click.option(
    "-o", "--output", type=click.Path(path_type=Path), help="Default: stdout."
)
def matrix_cli(output: Path | None) -> None:
    """Compliance matrix as Markdown (docs/ceos-compliance.md)."""
    from opera_vlm.product._ceos import compliance_matrix

    text = compliance_matrix()
    if output is None:
        click.echo(text, nl=False)
    else:
        output.write_text(text)
