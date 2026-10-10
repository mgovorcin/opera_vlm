# SPDX-FileCopyrightText: 2026 California Institute of Technology ("Caltech")
# SPDX-License-Identifier: Apache-2.0
# Part of opera-vlm, https://github.com/mgovorcin/opera-vlm.
"""Regression on a 128 x 128 synthetic asc/desc frame (plan T56.4).

The repo's in-tree golden: a change that moves any of these numbers changes
what a run produces. Update them deliberately, with the reason in the PR body
and a **[product]** CHANGELOG entry (CLAUDE.md, golden policy).
"""

from __future__ import annotations

import numpy as np
import pytest
from synthetic import make_frame, runconfig_dict

from opera_vlm.algorithm import run_algorithm
from opera_vlm.config import AlgorithmParameters, RunConfig

#: last pair (T0, T14): layer -> (nansum, value at [64, 64], value at [5, 1])
EXPECTED = {
    "vertical": (-33.029765110422964, -0.009237538042345296, -0.0015968624191466652),
    "vertical_std": (152.32396586930153, 0.009203147594462202, 0.012883492950260096),
    "east": (-88.1353451995466, -0.006031717168444907, np.nan),
    "east_std": (189.41483108953818, 0.011837616566922931, np.nan),
}


@pytest.mark.slow
def test_synthetic_128_regression(tmp_path):
    frame = make_frame(tmp_path / "f", n=128, posting=300.0, n_epochs=16, seed=7)
    params = tmp_path / "algorithm_parameters.yaml"
    AlgorithmParameters().to_yaml(params)
    wf = RunConfig.model_validate(runconfig_dict(frame, tmp_path, params)).to_workflow()
    results = list(run_algorithm(wf))
    assert len(results) == 14
    ds = results[-1].layers
    for name, (total, centre, edge) in EXPECTED.items():
        v = ds[name].values
        np.testing.assert_allclose(
            [np.nansum(v), v[64, 64], v[5, 1]], [total, centre, edge], rtol=1e-6
        )
    mode, counts = np.unique(ds["mode"].values, return_counts=True)
    assert dict(zip(mode.tolist(), counts.tolist(), strict=True)) == {1: 16000, 2: 384}
