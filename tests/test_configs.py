# SPDX-FileCopyrightText: 2026 California Institute of Technology ("Caltech")
# SPDX-License-Identifier: Apache-2.0
# Part of opera-vlm, https://github.com/mgovorcin/opera-vlm.
"""The committed configs/ are generated from the models: catch drift."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest

from opera_vlm.config import AlgorithmParameters, RunConfig

CONFIGS = Path(__file__).parents[1] / "configs"


def _yaml(model) -> str:
    buf = StringIO()
    model.to_yaml(buf)
    return buf.getvalue()


@pytest.mark.parametrize(
    ("name", "model"),
    [
        ("runconfig.yaml", lambda: RunConfig.construct_empty()),
        ("algorithm_parameters.yaml", lambda: AlgorithmParameters()),
    ],
)
def test_committed_config_is_current(name, model):
    path = CONFIGS / name
    if not path.exists():
        pytest.fail(f"{path} missing: run `pixi run gen-configs`")
    assert path.read_text() == _yaml(
        model()
    ), f"{name} is stale: run `pixi run gen-configs`"


def test_default_algorithm_parameters_load():
    AlgorithmParameters.from_yaml(CONFIGS / "algorithm_parameters.yaml")
