# SPDX-FileCopyrightText: 2026 California Institute of Technology ("Caltech")
# SPDX-License-Identifier: Apache-2.0
# Part of opera-vlm, https://github.com/mgovorcin/opera-vlm.
"""Context layers: GIA vertical rate and rigid plate motion (plan T56.3).

Neither is removed from the product. VLM is absolute in IGS20 (PRD A6); the
layers let a user subtract them:

- **plate motion**: east and north velocity of the frame's plate in
  ITRF2020-PMM (`geepers.euler.plate_velocity_enu`). A rigid rotation has no
  vertical component, so it matters for `east`; subtracting it gives a
  plate-fixed east. The plate comes from Venti's frame-parameter table
  (NA by default, PA for Hawaii, CA for Puerto Rico) unless
  `context_options.plate` names one.
- **GIA**: the vertical rate of a glacial isostatic adjustment model
  (ICE-6G_D, Peltier et al. 2018, doi:10.1002/2016JB013844), a regular
  lat/lon NetCDF, interpolated bilinearly. Only when
  `static_ancillary_file_group.gia_model_file` is given.

Rates are returned in meters per year on the grid they are asked for.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from opera_vlm.errors import InputValidationError
from opera_vlm.stack import Grid

_LAT = ("lat", "Lat", "latitude", "Latitude")
_LON = ("lon", "Lon", "longitude", "Longitude")


def lonlat(grid: Grid) -> tuple[np.ndarray, np.ndarray]:
    """Return the longitude and latitude (degrees) of every pixel of `grid`."""
    from pyproj import Transformer

    xx, yy = np.meshgrid(grid.x, grid.y)
    to_ll = Transformer.from_crs(f"EPSG:{grid.epsg}", "EPSG:4326", always_xy=True)
    lon, lat = to_ll.transform(xx, yy)
    return np.asarray(lon), np.asarray(lat)


def frame_plate(frame_id: int) -> str:
    """Return the plate code of `frame_id` in Venti's frame-parameter table."""
    from venti.frames import load_frame_table

    overrides = load_frame_table().overrides_for(frame_id)
    return str(overrides["calibration_options"]["frame"]["plate"])


def plate_motion(
    grid: Grid, plate: str, model: str = "ITRF2020-PMM"
) -> tuple[np.ndarray, np.ndarray]:
    """Return the east and north rigid-plate velocity (m/yr) of `plate` on `grid`."""
    from geepers.euler import plate_velocity_enu

    lon, lat = lonlat(grid)
    try:
        # geepers takes points: pass them flat
        ve, vn, _ = plate_velocity_enu(
            lon.ravel(), lat.ravel(), plate, model  # type: ignore[arg-type]
        )
    except ValueError as e:
        raise InputValidationError(f"context_options.plate: {e}", 1002) from e
    shape = grid.shape
    return np.reshape(ve, shape) / 1000.0, np.reshape(vn, shape) / 1000.0


def _coord(ds, names: tuple[str, ...], path: Path) -> str:
    for n in names:
        if n in ds.coords or n in ds.dims:
            return n
    raise InputValidationError(f"{path.name}: no coordinate named any of {names}", 1003)


def gia_rate(path: Path, grid: Grid, variable: str = "Drad_250") -> np.ndarray:
    """Return the GIA vertical rate (m/yr) of `variable` in `path` on `grid`.

    The model is on a regular lat/lon grid in mm/yr; longitudes in 0-360 are
    wrapped to -180-180.
    """
    import xarray as xr

    with xr.open_dataset(path) as ds:
        if variable not in ds:
            raise InputValidationError(
                f"{path.name}: no variable {variable!r} (context_options.gia_variable);"
                f" has {sorted(ds.data_vars)}",
                1003,
            )
        lat_name, lon_name = _coord(ds, _LAT, path), _coord(ds, _LON, path)
        da = ds[variable].squeeze(drop=True).load()
    lon360 = da[lon_name].values
    da = da.assign_coords({lon_name: ((lon360 + 180.0) % 360.0) - 180.0})
    da = da.sortby([lat_name, lon_name])
    lon, lat = lonlat(grid)
    pts = {
        lon_name: xr.DataArray(lon.ravel(), dims="p"),
        lat_name: xr.DataArray(lat.ravel(), dims="p"),
    }
    rate = da.interp(pts, method="linear").values.reshape(grid.shape)
    return rate / 1000.0
