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
    "vertical": (-33.028425144710155, -0.00923753809183836, -0.0015968624502420425),
    "vertical_std": (109.31737028062344, 0.006604565307497978, 0.009245047345757484),
    "east": (-88.10565088200383, -0.006031717173755169, np.nan),
    "east_std": (135.91259640455246, 0.008495137095451355, np.nan),
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
    assert dict(zip(mode.tolist(), counts.tolist(), strict=True)) == {
        0: 4,  # the synthetic water corner
        1: 15994,
        2: 386,
    }
