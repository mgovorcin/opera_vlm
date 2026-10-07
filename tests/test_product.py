# SPDX-FileCopyrightText: 2026 California Institute of Technology ("Caltech")
# SPDX-License-Identifier: Apache-2.0
# Part of opera-vlm, https://github.com/mgovorcin/opera-vlm.
from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np

from opera_vlm.config import RunConfig
from opera_vlm.main import run
from opera_vlm.product import LAYERS
from opera_vlm.product._layers import round_mantissa
from opera_vlm.validate import compare_products


def _product(runconfig_file: Path) -> Path:
    rc = RunConfig.from_yaml_file(runconfig_file)
    return run(rc.to_workflow(), pge_runconfig=runconfig_file.read_text())


def test_product_structure(runconfig_file: Path):
    path = _product(runconfig_file)
    with h5py.File(path) as f:
        for spec in LAYERS:
            assert spec.name in f
            assert f[spec.name].dtype == np.dtype(spec.dtype)
            assert "units" in f[spec.name].attrs
        assert "identification/product_version" in f
        assert "metadata/algorithm_parameters_yaml" in f
        assert "metadata/pge_runconfig" in f


def test_product_validates_against_itself(runconfig_file: Path):
    path = _product(runconfig_file)
    report = compare_products(path, path)
    assert report.passed, report.failures


def test_validate_detects_difference(runconfig_file: Path, tmp_path: Path):
    golden = _product(runconfig_file)
    test = tmp_path / "test.nc"
    test.write_bytes(golden.read_bytes())
    with h5py.File(test, "a") as f:
        f[LAYERS[0].name][0, 0] = 1e6
    assert not compare_products(golden, test).passed


def test_round_mantissa_bounded_error():
    rng = np.random.default_rng(0)
    x = rng.normal(size=1000).astype(np.float32)
    x[0] = np.nan
    y = round_mantissa(x, keep_bits=10)
    assert np.isnan(y[0])
    rel = np.abs((y[1:] - x[1:]) / x[1:])
    assert rel.max() <= 2.0**-10
