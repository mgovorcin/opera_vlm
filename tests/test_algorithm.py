# SPDX-FileCopyrightText: 2026 California Institute of Technology ("Caltech")
# SPDX-License-Identifier: Apache-2.0
# Part of opera-vlm, https://github.com/mgovorcin/opera-vlm.
"""The VLM workflow on a synthetic asc/desc frame with known truth (plan T56)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import h5py
import numpy as np
import pytest
from synthetic import _years, make_frame, runconfig_dict

from opera_vlm.algorithm import coarse_grid, run_algorithm, target_epochs, warp
from opera_vlm.config import AlgorithmParameters, RunConfig
from opera_vlm.errors import AlgorithmError, InputValidationError
from opera_vlm.main import run
from opera_vlm.stack import GeometryStack, Grid


def _workflow(frame, tmp_path: Path, params: AlgorithmParameters | None = None, **rc):
    path = tmp_path / "algorithm_parameters.yaml"
    (params or AlgorithmParameters()).to_yaml(path)
    data = runconfig_dict(frame, tmp_path, path)
    for group, values in rc.items():
        data.setdefault(group, {}).update(values)
    return RunConfig.model_validate(data).to_workflow()


@pytest.fixture(scope="module")
def frame(tmp_path_factory):
    return make_frame(tmp_path_factory.mktemp("frame"), n=24, n_epochs=12)


def _truth(frame, result):
    xx, yy = np.meshgrid(frame.x, frame.y)
    ve, _, vu = frame.velocity(xx, yy)
    dt = _years(result.reference_datetime, result.secondary_datetime)
    return ve * dt / 1000.0, vu * dt / 1000.0


def test_recovers_vertical_and_east(frame, tmp_path):
    """Both looks: WLS east/up within 1 mm; desc-less edge columns are projected."""
    results = list(run_algorithm(_workflow(frame, tmp_path)))
    assert len(results) == 10  # 11 targets every 12 days -> 10 pairs from T0
    assert all(r.reference_datetime == results[0].reference_datetime for r in results)
    # the descending grid starts 3.5 pixels east: 3 columns have one look only
    mode = results[0].layers["mode"].values
    assert (mode[:, :3] == 2).all() and (mode[:-2, 4:] == 1).all()
    assert (mode[-2:, -2:] == 0).all()  # water
    for r in (results[0], results[4]):
        east, up = _truth(frame, r)
        ds = r.layers
        wls = ds["mode"].values == 1
        err_up = np.abs(ds["vertical"].values - up)
        assert np.median(err_up[wls]) < 0.5e-3
        assert err_up[wls].max() < 1.5e-3
        assert np.abs(ds["east"].values - east)[wls].max() < 1.5e-3
        assert np.isnan(ds["east"].values[~wls]).all()  # projection solves no east
        assert np.nanmax(err_up[~wls]) < 2.5e-3  # projection with GNSS east/north
        sig = ds["vertical_std"].values
        assert np.isfinite(sig[wls | (ds["mode"].values == 2)]).all()
        proj = ds["mode"].values == 2
        assert np.median(sig[proj]) > np.median(sig[wls])


def test_water_is_masked(frame, tmp_path):
    """Pixels the DISP water_mask flags are no data (mode 0) in every product."""
    r = next(iter(run_algorithm(_workflow(frame, tmp_path))))
    mode = r.layers["mode"].values
    assert (mode[-2:, -2:] == 0).all()
    assert np.isnan(r.layers["vertical"].values[-2:, -2:]).all()
    params = AlgorithmParameters().with_overrides(
        {"input_options": {"mask_layers": ["recommended_mask"]}}
    )
    with pytest.raises(InputValidationError, match="no mask layer 'recommended_mask'"):
        next(iter(run_algorithm(_workflow(frame, tmp_path, params))))


def test_single_geometry_projects_everywhere(frame, tmp_path):
    wf = _workflow(frame, tmp_path)
    inputs = wf.input_file_group.model_copy(
        update={"descending_disp_files": [], "descending_cal_files": []}
    )
    wf = wf.model_copy(update={"input_file_group": inputs})
    r = next(iter(run_algorithm(wf)))
    _, up = _truth(frame, r)
    land = np.ones(r.layers["mode"].shape, bool)
    land[-2:, -2:] = False
    assert (r.layers["mode"].values[land] == 2).all()
    assert np.isnan(r.layers["east"].values).all()
    assert np.nanmax(np.abs(r.layers["vertical"].values - up)) < 2.5e-3
    assert r.ceos["orbit_pass_direction"] == "Ascending"


def test_missing_cal_product_fails(frame, tmp_path):
    wf = _workflow(frame, tmp_path)
    inputs = wf.input_file_group.model_copy(
        update={"ascending_cal_files": frame.asc_cal[1:]}
    )
    wf = wf.model_copy(update={"input_file_group": inputs})
    with pytest.raises(InputValidationError, match="1003.*no DISP-CAL product"):
        next(iter(run_algorithm(wf)))


def test_unchainable_stack_fails(frame):
    # drop the pair that ends on the second block's reference date
    block_ref = sorted(
        {p.reference for p in GeometryStack(frame.asc_disp, frame.asc_cal).pairs}
    )[1]
    keep = [p for p in frame.asc_disp if f"_{block_ref:%Y%m%dT%H%M%S}Z_v" not in p.name]
    assert len(keep) == len(frame.asc_disp) - 1
    with pytest.raises(InputValidationError, match="cannot be chained"):
        GeometryStack(keep, frame.asc_cal)


def test_chaining_adds_block_links(frame):
    stack = GeometryStack(frame.asc_disp, frame.asc_cal)
    rows = slice(0, 4)
    last = stack.pairs[-1]
    cum = stack.read_cumulative([last.secondary], rows)[0]
    link = stack._pair_rows(  # the block's reference pair, then the pair itself
        next(p for p in stack.pairs if p.secondary == last.reference), rows
    )
    np.testing.assert_allclose(cum, link + stack._pair_rows(last, rows))
    assert stack.read_cumulative([stack.origin], rows).max() == 0.0


def test_provenance_mismatch_fails(tmp_path):
    other = make_frame(tmp_path / "f", n=12, n_epochs=6, buffer_meters=0.0)
    with pytest.raises(InputValidationError, match="1003"):
        next(iter(run_algorithm(_workflow(other, tmp_path))))


def test_missing_provenance_needs_opt_out(tmp_path):
    other = make_frame(tmp_path / "f", n=12, n_epochs=6, buffer_meters=None)
    with pytest.raises(InputValidationError, match="gnss_provenance"):
        next(iter(run_algorithm(_workflow(other, tmp_path))))
    params = AlgorithmParameters().with_overrides(
        {"gnss_options": {"require_provenance_match": False}}
    )
    r = next(iter(run_algorithm(_workflow(other, tmp_path, params))))
    assert (r.layers["mode"].values[:-2] > 0).all()


def test_gnss_needs_a_source(frame, tmp_path):
    wf = _workflow(frame, tmp_path)
    inputs = wf.input_file_group.model_copy(update={"unr_grid_latlon_file": None})
    wf = wf.model_copy(update={"input_file_group": inputs})
    with pytest.raises(InputValidationError, match="no GNSS horizontal field"):
        next(iter(run_algorithm(wf)))


def test_velocity_product_not_implemented(frame, tmp_path):
    wf = _workflow(frame, tmp_path)
    wf = wf.model_copy(
        update={"output_options": {**wf.output_options, "write_velocity_product": True}}
    )
    with pytest.raises(AlgorithmError, match="write_velocity_product"):
        next(iter(run_algorithm(wf)))


def test_target_epochs_cover_the_common_span(frame):
    asc = GeometryStack(frame.asc_disp, frame.asc_cal)
    desc = GeometryStack(frame.desc_disp, frame.desc_cal, name="descending")
    t = target_epochs([asc, desc], 12.0)
    assert t[0] == datetime(2020, 1, 7)  # the later start (descending)
    assert t[-1] <= asc.pairs[-1].secondary
    with pytest.raises(InputValidationError, match="fewer than two"):
        target_epochs([asc, desc], 400.0)


def test_first_target_needs_every_geometry(frame, caplog):
    """A geometry without enough epochs at T0 would be lost from every product:
    the first target moves to the first epoch where both have data."""
    asc = GeometryStack(frame.asc_disp, frame.asc_cal)
    desc = GeometryStack(frame.desc_disp, frame.desc_cal, name="descending")
    # +-20 days around the descending start (2020-01-07) holds only 2
    # descending epochs; the first epoch with 3 of each look is the ascending
    # 2020-01-13 (desc 01-07, 01-19, 01-31; asc 01-01, 01-13, 01-25)
    t = target_epochs([asc, desc], 12.0, window_days=40.0, min_points=3)
    assert t[0] == datetime(2020, 1, 13)
    assert "first target moved" in caplog.text
    assert target_epochs([asc, desc], 12.0, 40.0, 1)[0] == datetime(2020, 1, 7)
    with pytest.raises(InputValidationError, match="no epoch"):
        target_epochs([asc, desc], 12.0, window_days=1.0, min_points=3)


def test_warp_and_coarse_grid():
    """The two warps a run does are exact on a plane: coarse GNSS -> product
    grid (the coarse centres span the product grid), and a shifted grid of the
    same posting (descending -> ascending), NaN outside its footprint."""
    x = 1000.0 + 100.0 * np.arange(10)
    y = 5000.0 - 100.0 * np.arange(8)
    g = Grid(x=x, y=y, epsg=32615)

    def plane(grid):
        return np.add.outer(0.5 * grid.y, 2.0 * grid.x)

    same = plane(g)
    assert warp(same, g, g) is same  # same grid: no resampling
    c = coarse_grid(g, 300.0)
    assert c.x[0] == x[0] and c.x[-1] == x[-1] and c.x.size == 4
    np.testing.assert_allclose(warp(plane(c), c, g), plane(g), rtol=1e-9)

    shifted = Grid(x=x + 250.0, y=y, epsg=32615)
    out = warp(plane(shifted), shifted, g)
    assert np.isnan(out[:, :2]).all()  # west of the shifted footprint
    np.testing.assert_allclose(out[:, 3:-1], plane(g)[:, 3:-1], rtol=1e-9)


def test_products_one_per_pair(frame, tmp_path):
    products = run(_workflow(frame, tmp_path))
    assert len(products) == 10
    names = [p.name.split("_")[4:6] for p in products]
    assert len({n[0] for n in names}) == 1 and len({n[1] for n in names}) == 10
    with h5py.File(products[0]) as f:
        assert f["identification/number_of_looks"][()] == 2
        assert len(f["identification/gnss_provenance_digest"][()]) == 64


def test_row_blocks_cover_every_row_once():
    from opera_vlm.algorithm import row_blocks

    for ny, size in ((10, 4), (9, 4), (1025, 512), (3, 512), (513, 512)):
        blocks = row_blocks(ny, size)
        rows = [r for b in blocks for r in range(b.start, b.stop)]
        assert rows == list(range(ny))
        assert all(b.stop - b.start >= 2 for b in blocks) or ny < 2
