# SPDX-FileCopyrightText: 2026 California Institute of Technology ("Caltech")
# SPDX-License-Identifier: Apache-2.0
# Part of opera-vlm, https://github.com/mgovorcin/opera-vlm.
from __future__ import annotations

from pathlib import Path

import pytest

from opera_vlm.config import AlgorithmParameters, RunConfig
from opera_vlm.config.pge_runconfig import PATH_INPUTS


@pytest.fixture
def algorithm_parameters_file(tmp_path: Path) -> Path:
    path = tmp_path / "algorithm_parameters.yaml"
    AlgorithmParameters().to_yaml(path)
    return path


@pytest.fixture
def runconfig_file(tmp_path: Path, algorithm_parameters_file: Path) -> Path:
    """A valid runconfig whose path inputs are empty placeholder files/dirs.

    Replace the placeholders with real (small) test data once the algorithm
    reads its inputs; keep the fixture as the single place tests get a config.
    """
    rc = RunConfig.construct_empty()
    for group_name, field, kind in PATH_INPUTS:
        group = getattr(rc, group_name)
        info = type(group).model_fields[field]
        if field == "algorithm_parameters_file":
            setattr(group, field, algorithm_parameters_file)
            continue
        if not info.is_required() and not field.endswith("_files"):
            continue
        path = tmp_path / "inputs" / field
        if kind == "dir":
            path.mkdir(parents=True, exist_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
        value = [path] if isinstance(getattr(group, field), list) else path
        object.__setattr__(group, field, value)
    rc.product_path_group.output_path = tmp_path / "output"
    rc.product_path_group.product_path = tmp_path / "output"
    rc.product_path_group.scratch_path = tmp_path / "scratch"
    path = tmp_path / "runconfig.yaml"
    # Round-trip through validation so the fixture is a *valid* runconfig
    RunConfig.model_validate(rc.model_dump(by_alias=True)).to_yaml(path)
    return path
