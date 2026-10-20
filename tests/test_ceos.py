# SPDX-FileCopyrightText: 2026 California Institute of Technology ("Caltech")
# SPDX-License-Identifier: Apache-2.0
# Part of opera-vlm, https://github.com/mgovorcin/opera-vlm.
"""CEOS-ARD: the declaration, the generated matrix, and what products contain."""

from __future__ import annotations

from pathlib import Path

import pytest

from opera_vlm.config import RunConfig
from opera_vlm.main import run
from opera_vlm.product._ceos import (
    CEOS_ENABLED,
    CEOS_FIELDS,
    CEOS_STATIC,
    check_compliance,
    compliance_matrix,
    is_compliant,
)

DOC = Path(__file__).parents[1] / "docs" / "ceos-compliance.md"

pytestmark = pytest.mark.skipif(
    not CEOS_ENABLED, reason="product does not claim CEOS-ARD"
)


def test_field_names_unique():
    names = [f.name for f in CEOS_FIELDS]
    assert len(names) == len(set(names))


def test_static_values_declared():
    static = {f.name for f in CEOS_FIELDS if f.source == "static"}
    assert set(CEOS_STATIC) == static


def test_matrix_doc_is_current():
    assert DOC.exists(), "run `pixi run gen-configs`"
    assert DOC.read_text() == compliance_matrix(), "stale: run `pixi run gen-configs`"


def test_product_ceos_fields(runconfig_file: Path):
    rc = RunConfig.from_yaml_file(runconfig_file)
    product = run(rc.to_workflow())[-1]
    status = {f.name: s for f, s in check_compliance(product)}
    for f in CEOS_FIELDS:
        if f.source == "computed":
            assert status[f.name] == "ok", f.name
        elif f.source == "static":
            expected = "ok" if CEOS_STATIC.get(f.name) not in ("", None) else "missing"
            assert status[f.name] == expected, f.name
    # runtime fields come from the inputs (satellites, orbit, incidence angles)
    assert all(status[f.name] == "ok" for f in CEOS_FIELDS if f.source == "runtime")


def test_ungridded_product_not_compliant(runconfig_file: Path, tmp_path: Path):
    import h5py

    rc = RunConfig.from_yaml_file(runconfig_file)
    product = run(rc.to_workflow())[-1]
    broken = tmp_path / "ungridded.nc"
    broken.write_bytes(product.read_bytes())
    with h5py.File(broken, "a") as f:
        del f["vertical"].attrs["grid_mapping"]
    report = check_compliance(broken)
    status = {f.name: s for f, s in report}
    assert status["product_coordinate_reference_system"] == "ungridded"
    assert not is_compliant(report)
    intact = {f.name: s for f, s in check_compliance(product)}
    assert intact["product_coordinate_reference_system"] == "ok"
