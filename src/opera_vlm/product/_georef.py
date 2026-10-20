# SPDX-FileCopyrightText: 2026 California Institute of Technology ("Caltech")
# SPDX-License-Identifier: Apache-2.0
# Part of opera-vlm, https://github.com/mgovorcin/opera-vlm.
"""Georeferencing of the product grid: CF grid mapping + GDAL geotransform.

Every 2-D layer carries ``grid_mapping = "spatial_ref"``; the scalar
``spatial_ref`` variable holds the CRS as CF grid-mapping attributes, the WKT
(``crs_wkt`` for CF, ``spatial_ref`` for GDAL) and the GDAL ``GeoTransform``
of the pixel-centre ``x``/``y`` axes. This is the layout DISP-S1 and DISP-CAL
use, so GDAL, rioxarray and CF readers place the layers without the global
``epsg`` attribute.
"""

from __future__ import annotations

import numpy as np
import xarray as xr
from pyproj import CRS

GRID_MAPPING = "spatial_ref"


def crs_label(epsg: int) -> str:
    """``EPSG:<code> (<name>)``, the CEOS coordinate-reference-system value."""
    return f"EPSG:{int(epsg)} ({CRS.from_epsg(int(epsg)).name})"


def geotransform(x: np.ndarray, y: np.ndarray) -> str:
    """GDAL GeoTransform (outer pixel edges) of pixel-centre axes."""
    dx = float(x[1] - x[0]) if x.size > 1 else 1.0
    dy = float(y[1] - y[0]) if y.size > 1 else -1.0
    return " ".join(
        repr(v) for v in (float(x[0]) - dx / 2, dx, 0.0, float(y[0]) - dy / 2, 0.0, dy)
    )


def add_grid_mapping(ds: xr.Dataset, epsg: int) -> xr.Dataset:
    """Return ``ds`` with ``spatial_ref``, ``grid_mapping`` and CF x/y attributes."""
    crs = CRS.from_epsg(int(epsg))
    wkt = crs.to_wkt()
    attrs = {
        **crs.to_cf(),
        "crs_wkt": wkt,
        "spatial_ref": wkt,
        "GeoTransform": geotransform(ds["x"].values, ds["y"].values),
    }
    out = ds.copy()
    out[GRID_MAPPING] = xr.DataArray(np.int32(0), attrs=attrs)
    for name, da in out.data_vars.items():
        if da.dims == ("y", "x"):
            out[name] = da.assign_attrs(grid_mapping=GRID_MAPPING)
    unit = crs.axis_info[0].unit_name if crs.axis_info else ""
    units = "m" if unit in ("metre", "meter") else unit
    projected = crs.is_projected
    for axis, long in (("x", "x coordinate"), ("y", "y coordinate")):
        std = (
            f"projection_{axis}_coordinate"
            if projected
            else ("longitude" if axis == "x" else "latitude")
        )
        out[axis] = out[axis].assign_attrs(
            standard_name=std,
            long_name=f"{long} of projection (pixel centre)" if projected else std,
            units=(
                units
                if projected
                else ("degrees_east" if axis == "x" else "degrees_north")
            ),
        )
    return out


def georef_problems(h5) -> list[str]:
    """Why an open product (h5py.File) is not georeferenced; empty when it is."""
    problems = []
    if GRID_MAPPING not in h5 or "crs_wkt" not in h5[GRID_MAPPING].attrs:
        problems.append(f"no '{GRID_MAPPING}' variable with crs_wkt")
    for name, obj in h5.items():
        if name in (GRID_MAPPING, "x", "y") or not hasattr(obj, "ndim"):
            continue
        if obj.ndim == 2:
            gm = obj.attrs.get("grid_mapping")
            gm = gm.decode() if isinstance(gm, bytes) else gm
            if gm != GRID_MAPPING:
                problems.append(f"layer '{name}' has no grid_mapping")
    return problems
