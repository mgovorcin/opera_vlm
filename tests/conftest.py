# SPDX-FileCopyrightText: 2026 California Institute of Technology ("Caltech")
# SPDX-License-Identifier: Apache-2.0
# Part of opera-vlm, https://github.com/mgovorcin/opera-vlm.
from __future__ import annotations

from pathlib import Path

import pytest
from synthetic import make_frame, runconfig_dict

from opera_vlm.config import AlgorithmParameters, RunConfig


@pytest.fixture
def algorithm_parameters_file(tmp_path: Path) -> Path:
    path = tmp_path / "algorithm_parameters.yaml"
    AlgorithmParameters().to_yaml(path)
    return path


@pytest.fixture
def runconfig_file(tmp_path: Path, algorithm_parameters_file: Path) -> Path:
    """A valid runconfig on a small synthetic asc/desc frame (tests/synthetic.py)."""
    frame = make_frame(tmp_path / "inputs", n=16, n_epochs=8)
    rc = RunConfig.model_validate(
        runconfig_dict(frame, tmp_path, algorithm_parameters_file)
    )
    path = tmp_path / "runconfig.yaml"
    rc.to_yaml(path)
    return path
