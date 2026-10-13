# SPDX-FileCopyrightText: 2026 California Institute of Technology ("Caltech")
# SPDX-License-Identifier: Apache-2.0
# Part of opera-vlm, https://github.com/mgovorcin/opera-vlm.
"""Context layers: rigid plate motion and GIA (plan T56.3)."""

from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np
import pytest
import xarray as xr
from synthetic import make_frame, runconfig_dict

from opera_vlm.algorithm import run_algorithm
from opera_vlm.config import AlgorithmParameters, RunConfig
from opera_vlm.context import frame_plate, gia_rate, lonlat, plate_motion
from opera_vlm.errors import InputValidationError
from opera_vlm.main import run
from opera_vlm.stack import Grid

GRID = Grid(
    x=250_000.0 + 1000.0 * (np.arange(20) + 0.5),
    y=3_300_000.0 - 1000.0 * (np.arange(15) + 0.5),
    epsg=32615,
)


def _ice6g(path: Path) -> Path:
    """A global 1-degree model on 0-360 longitudes, linear near the test frame."""
    lat = np.arange(-89.5, 90.0, 1.0)
    lon = np.arange(0.5, 360.0, 1.0)
    rate = 0.05 * lat[:, None] + 0.02 * lon[None, :]  # mm/yr
    xr.Dataset(
        {"Drad_250": (("Lat", "Lon"), rate)}, coords={"Lat": lat, "Lon": lon}
    ).to_netcdf(path, engine="h5netcdf")
    return path


def test_plate_motion_matches_geepers():
    from geepers.euler import plate_velocity_enu

    ve, vn = plate_motion(GRID, "NA")
    lon, lat = lonlat(GRID)
    e, n, _ = plate_velocity_enu(lon.ravel(), lat.ravel(), "NA")
    np.testing.assert_allclose(ve.ravel(), e / 1000.0)
    np.testing.assert_allclose(vn.ravel(), n / 1000.0)
    assert ve.shape == GRID.shape
    # North America in ITRF2020 near Houston: ~-14 mm/yr east, ~-2 mm/yr north
    assert -0.02 < ve.mean() < -0.008 and -0.006 < vn.mean() < 0.002
    pa, _ = plate_motion(GRID, "PA")
    assert not np.allclose(pa, ve)
    with pytest.raises(InputValidationError, match="1002"):
        plate_motion(GRID, "XX")


def test_frame_plate_from_the_venti_table():
    assert frame_plate(8882) == "NA"  # the table default
    assert frame_plate(23211) == "PA"  # Hawaii
    assert frame_plate(35991) == "CA"  # Puerto Rico


def test_gia_rate_wraps_longitudes_and_interpolates(tmp_path):
    path = _ice6g(tmp_path / "ice6g.nc")
    lon, lat = lonlat(GRID)
    truth = (0.05 * lat + 0.02 * (lon + 360.0)) / 1000.0
    np.testing.assert_allclose(gia_rate(path, GRID), truth, rtol=1e-9)
    with pytest.raises(InputValidationError, match="no variable"):
        gia_rate(path, GRID, "missing")


@pytest.fixture(scope="module")
def frame(tmp_path_factory):
    return make_frame(tmp_path_factory.mktemp("frame"), n=12, n_epochs=6)


def _workflow(frame, tmp_path, params=None, gia=None):
    p = tmp_path / "ap.yaml"
    (params or AlgorithmParameters()).to_yaml(p)
    data = runconfig_dict(frame, tmp_path, p)
    if gia is not None:
        data["static_ancillary_file_group"] = {"gia_model_file": str(gia)}
    return RunConfig.model_validate(data).to_workflow()


def test_products_carry_the_context_layers(frame, tmp_path):
    gia = _ice6g(tmp_path / "ice6g.nc")
    product = run(_workflow(frame, tmp_path, gia=gia))[0]
    with h5py.File(product) as f:
        for name in ("plate_motion_east_rate", "plate_motion_north_rate"):
            assert np.isfinite(f[name][()]).all()
            assert f[name].attrs["units"] == "meters / year"
        assert np.isfinite(f["gia_vertical_rate"][()]).all()
        assert f["identification/plate"][()] == b"NA"
        assert f["identification/gia_model"][()] == b"ice6g.nc"


def test_no_gia_file_no_gia_layer_and_plate_override(frame, tmp_path):
    params = AlgorithmParameters().with_overrides({"context_options": {"plate": "PA"}})
    r = next(iter(run_algorithm(_workflow(frame, tmp_path, params))))
    assert "gia_vertical_rate" not in r.layers
    assert r.identification["plate"] == "PA"
    ve, _ = plate_motion(Grid(frame.x, frame.y, 32615), "PA")
    np.testing.assert_allclose(
        r.layers["plate_motion_east_rate"].values, ve, rtol=1e-4, atol=1e-7
    )
