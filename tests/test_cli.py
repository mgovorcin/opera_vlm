# SPDX-FileCopyrightText: 2026 California Institute of Technology ("Caltech")
# SPDX-License-Identifier: Apache-2.0
# Part of opera-vlm, https://github.com/mgovorcin/opera-vlm.
from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from opera_vlm.cli import cli_app
from opera_vlm.errors import ExitCode


def invoke(*args: str):
    return CliRunner().invoke(cli_app, list(args), catch_exceptions=False)


def test_help_and_version():
    assert invoke("--help").exit_code == 0
    result = invoke("--version")
    assert result.exit_code == 0


@pytest.mark.parametrize(
    "sub", [["template"], ["algorithm"], ["schema"], ["schema", "--algorithm"]]
)
def test_config_commands(sub):
    result = invoke("config", *sub)
    assert result.exit_code == 0, result.output
    assert result.output.strip()


def test_algorithm_set_rejects_unknown_key():
    result = CliRunner().invoke(
        cli_app, ["config", "algorithm", "--set", "nope.nope=1"]
    )
    assert result.exit_code != 0


def test_run_bad_runconfig_exit_code(tmp_path: Path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("opera_vlm_workflow:\n  not_a_group: 1\n")
    result = CliRunner().invoke(cli_app, ["run", str(bad)])
    assert result.exit_code == ExitCode.RUNCONFIG_ERROR


@pytest.mark.slow
def test_run_end_to_end(runconfig_file: Path, tmp_path: Path):
    result = CliRunner().invoke(cli_app, ["run", str(runconfig_file)])
    assert result.exit_code == 0, result.output
    products = sorted((tmp_path / "output").glob("OPERA_*.nc"))
    assert len(products) > 1  # one per target pair
    assert all(p.with_suffix(".png").exists() for p in products)
    assert (tmp_path / "output" / "opera_vlm.log").exists()
