# SPDX-FileCopyrightText: 2026 California Institute of Technology ("Caltech")
# SPDX-License-Identifier: Apache-2.0
# Part of opera-vlm, https://github.com/mgovorcin/opera-vlm.
from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

__all__ = ["run_cli", "run_main"]

logger = logging.getLogger("opera_vlm")


def run_main(config_file: str | Path, debug: bool = False) -> Path:
    """Load the runconfig, set up logging and threads, and run the job."""
    # Lazy imports: `--help` stays fast, and the thread variables are set
    # before numpy/GDAL are imported by the processing modules.
    from opera_vlm._log import log_run_header, setup_logging
    from opera_vlm.config import RunConfig

    config_file = Path(config_file)
    runconfig = RunConfig.from_yaml_file(config_file)
    runconfig.worker_settings.apply_thread_env()
    setup_logging(
        level="DEBUG" if debug else "INFO", filename=runconfig.resolved_log_file()
    )
    log_run_header(logger, sys.argv)
    logger.info("Runconfig: %s", config_file.resolve())

    workflow = runconfig.to_workflow()

    from opera_vlm.main import run

    return run(workflow, pge_runconfig=config_file.read_text())


@click.command("run")
@click.argument(
    "config_file", type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
@click.pass_context
def run_cli(ctx: click.Context, config_file: Path) -> None:
    """Run the SAS on the PGE runconfig CONFIG_FILE.

    Exit codes: 0 success, 1 unexpected error, 3 invalid runconfig,
    4 input validation, 5 algorithm, 6 product (see docs/error-codes.md).
    """
    from opera_vlm.errors import ExitCode, SasError

    try:
        run_main(config_file, debug=ctx.obj.get("debug", False))
    except SasError as e:
        logger.error("%s: %s", type(e).__name__, e)
        logger.debug("Traceback:", exc_info=True)
        if not logger.handlers:  # failed before logging was set up
            click.echo(f"ERROR {type(e).__name__}: {e}", err=True)
        ctx.exit(int(e.exit_code))
    except Exception:
        logger.exception("Unexpected error")
        if not logger.handlers:
            raise
        ctx.exit(int(ExitCode.UNEXPECTED_ERROR))
