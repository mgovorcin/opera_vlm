# SPDX-FileCopyrightText: 2026 California Institute of Technology ("Caltech")
# SPDX-License-Identifier: Apache-2.0
# Part of opera-vlm, https://github.com/mgovorcin/opera-vlm.
"""The science algorithm: calibrated DISP (asc/desc) -> vertical per pair.

One run processes the stacks of one ascending frame (and optionally one
descending frame) and yields one `AlgorithmResult` per target pair
``(T0, Tk)`` (plan T56.2; per-pair VLM is the official product, ADR 0001):

1. **Target epochs** every `temporal_options.target_spacing_days` over the
   span both geometries cover; ``T0`` is the first one and the reference of
   every product.
2. **Temporal resampling** (`venti.temporal.resample_timeseries`) of each
   geometry's chained calibrated displacement at ``T0`` and ``Tk`` on its own
   grid, row block by row block; the pair is ``R(Tk) - R(T0)``.
3. **Common grid**: the descending pair (and both LOS files) are resampled
   bilinearly onto the ascending grid, the product grid.
4. **GNSS horizontal** (`venti.gnss.vlm.load_gnss_for_vlm`, provenance
   checked against DISP-CAL) on a ~1 km grid, interpolated to the product
   grid and scaled to the pair (`pair_displacement`).
5. **Decomposition** (`venti.decomposition.decompose`): WLS east/up with
   north from GNSS where both looks are valid and well conditioned (mode 1),
   otherwise single-geometry projection with GNSS east and north (mode 2).

Per-look sigma of the pair (v0.1 model)::

    sigma^2 = s_fit(T0)^2 + s_fit(Tk)^2 + s_cal(T0)^2 + s_cal(Tk)^2 + sigma_disp^2
              + (sigma_rate * (Tk - T0))^2

``s_fit`` is the window-fit standard error, ``s_cal`` the DISP-CAL
``calibration_std`` of the epoch nearest the target and ``sigma_disp`` the
DISP noise below the calibration cutoff (TS-S1) and ``sigma_rate`` the rate
error chained per-pair calibration leaves (T57, fitted on LA real data).
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr

from opera_vlm.config import Workflow
from opera_vlm.errors import AlgorithmError, InputValidationError
from opera_vlm.stack import GeometryStack, Grid

logger = logging.getLogger(__name__)

#: Set to False once run_algorithm is implemented.
IS_PLACEHOLDER = False

#: Posting of the GNSS field before it is interpolated to the product grid.
GNSS_POSTING_METERS = 1000.0
#: Rows processed at a time (memory: window epochs x rows x columns).
ROW_BLOCK = 512


@dataclass
class AlgorithmResult:
    """Output of `run_algorithm` for one target pair.

    Attributes
    ----------
    layers : xr.Dataset
        One variable per `product.LAYERS` entry, dims ``(y, x)`` with ``x``/``y``
        coordinates (pixel centres) and a ``spatial_ref`` variable (rioxarray
        ``ds.rio.write_crs``) or an ``epsg`` attribute.
    reference_datetime, secondary_datetime : datetime or None
        Time span the product covers (used in the file name).
    source_files : list of str
        Input granule names, recorded in /identification.
    identification : dict
        Extra scalar /identification entries (orbit, track, bounding polygon...).
    ceos : dict
        Values of the ``runtime`` CEOS-ARD fields (`product._ceos.CEOS_FIELDS`):
        orbit direction, incidence angles, satellites of this job...

    """

    layers: xr.Dataset
    reference_datetime: datetime | None = None
    secondary_datetime: datetime | None = None
    source_files: list[str] = field(default_factory=list)
    identification: dict[str, Any] = field(default_factory=dict)
    ceos: dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------- grids
def warp(values: np.ndarray, src: Grid, dst: Grid) -> np.ndarray:
    """Bilinear resampling of `values` from `src` to `dst` (NaN = no data)."""
    if src.same_as(dst):
        return values
    from rasterio.warp import Resampling, reproject

    out = np.full(dst.shape, np.nan)
    reproject(
        np.asarray(values, dtype=np.float64),
        out,
        src_transform=src.transform,
        src_crs=f"EPSG:{src.epsg}",
        src_nodata=np.nan,
        dst_transform=dst.transform,
        dst_crs=f"EPSG:{dst.epsg}",
        dst_nodata=np.nan,
        resampling=Resampling.bilinear,
    )
    return out


def row_blocks(ny: int, size: int = ROW_BLOCK) -> list[slice]:
    """Row slices of at most `size` rows; none shorter than 2 (a grid needs a dy)."""
    starts = list(range(0, ny, size))
    if len(starts) > 1 and ny - starts[-1] < 2:
        starts.pop()
    return [slice(a, b) for a, b in zip(starts, [*starts[1:], ny], strict=True)]


def sub_grid(grid: Grid, rows: slice) -> Grid:
    """Return the rows `rows` of `grid` as a grid."""
    return Grid(x=grid.x, y=grid.y[rows], epsg=grid.epsg)


def coarse_grid(grid: Grid, posting: float) -> Grid:
    """Build a regular grid of about `posting` metres whose centres span `grid`."""

    def axis(v: np.ndarray) -> np.ndarray:
        n = max(2, int(np.ceil(abs(v[-1] - v[0]) / posting)) + 1)
        return np.linspace(v[0], v[-1], n)

    return Grid(x=axis(grid.x), y=axis(grid.y), epsg=grid.epsg)


def read_los(path: Path, dst: Grid) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """East, north, up LOS unit-vector components of a 3-band GeoTIFF on `dst`."""
    import rasterio

    with rasterio.open(path) as ds:
        if ds.count < 3:
            raise InputValidationError(
                f"{path.name}: expected 3 bands (east, north, up), got {ds.count}",
                1003,
            )
        enu = ds.read([1, 2, 3]).astype(np.float64)
        nodata = ds.nodata
        t = ds.transform
        x = t.c + t.a * (np.arange(ds.width) + 0.5)
        y = t.f + t.e * (np.arange(ds.height) + 0.5)
        src = Grid(x=x, y=y, epsg=int(ds.crs.to_epsg()))
    if nodata is not None and np.isfinite(nodata):
        enu[enu == nodata] = np.nan
    enu[:, ~np.isfinite(enu).all(axis=0)] = np.nan
    # float32 as on disk: the LOS is held for the whole run
    e, n, u = (warp(c, src, dst).astype(np.float32) for c in enu)
    return e, n, u


# ---------------------------------------------------------------- targets
def target_epochs(
    stacks: list[GeometryStack],
    spacing_days: float,
    window_days: float | None = None,
    min_points: int = 1,
) -> list[datetime]:
    """Targets every `spacing_days` over the span all `stacks` cover.

    With `window_days`, the first target (the reference of every product) is
    the first epoch at which every stack has `min_points` epochs within
    ``window_days / 2``: a geometry with no value at ``T0`` would be missing
    from every product of the run (NYC F30175, 2019). Later targets where a
    stack has too few epochs are dropped (no product): a gap in the
    acquisitions, e.g. no DISP in snow season (Montana F40308 / F07081).
    """
    start = max(np.datetime64(s.dates[0], "s") for s in stacks)
    end = min(np.datetime64(s.dates[-1], "s") for s in stacks)
    t0 = start.astype(datetime)
    t1 = end.astype(datetime)
    if window_days is not None:
        half = window_days / 2.0
        candidates = sorted(
            {t for s in stacks for t in s.dates.astype(datetime) if t0 <= t <= t1}
        )
        ok = [
            t
            for t in candidates
            if all(len(s.epochs_within(t, half)) >= min_points for s in stacks)
        ]
        if not ok:
            raise InputValidationError(
                f"no epoch from {t0:%Y-%m-%d} to {t1:%Y-%m-%d} has {min_points}"
                f" epochs of every geometry within {window_days:g} days",
                1003,
            )
        if ok[0] != t0:
            logger.warning(
                "first target moved from %s to %s: before it a geometry has fewer"
                " than %d epochs in the window",
                f"{t0:%Y-%m-%d}",
                f"{ok[0]:%Y-%m-%d}",
                min_points,
            )
        t0 = ok[0]
    out = []
    dropped = []
    t = t0
    while t <= t1:
        if window_days is None or all(
            len(s.epochs_within(t, window_days / 2.0)) >= min_points for s in stacks
        ):
            out.append(t)
        else:
            dropped.append(t)
        t += timedelta(days=spacing_days)
    if dropped:
        logger.warning(
            "%d target(s) without enough epochs of every geometry are skipped: %s",
            len(dropped),
            ", ".join(f"{d:%Y-%m-%d}" for d in dropped),
        )
    if len(out) < 2:
        raise InputValidationError(
            f"the stacks overlap from {t0:%Y-%m-%d} to {t1:%Y-%m-%d}: fewer than two"
            f" target epochs at {spacing_days:g}-day spacing",
            1003,
        )
    return out


def resample_at(
    stack: GeometryStack, target: datetime, workflow: Workflow
) -> tuple[np.ndarray, np.ndarray]:
    """Window-fit value and sigma (meters) of `stack` at `target`, full frame.

    The sigma includes the DISP-CAL ``calibration_std`` of the epoch nearest
    the target (module docstring).
    """
    from venti.temporal import resample_timeseries

    opts = workflow.algorithm_parameters.temporal_options
    epochs = stack.epochs_within(target, opts.window_days / 2.0)
    ny, nx = stack.grid.shape
    value = np.full((ny, nx), np.nan)
    sigma = np.full((ny, nx), np.nan)
    if len(epochs) < opts.min_points:
        logger.warning(
            "%s at %s: %d epochs in the window (< %d): no %s look for this target",
            stack.name,
            f"{target:%Y-%m-%d}",
            len(epochs),
            opts.min_points,
            stack.name,
        )
        return value, sigma
    logger.info(
        "%s at %s: %d epochs in the window",
        stack.name,
        f"{target:%Y-%m-%d}",
        len(epochs),
    )
    dates = np.array(epochs, dtype="datetime64[s]")
    nearest = stack.nearest_epoch(target)
    for r0 in range(0, ny, ROW_BLOCK):
        rows = slice(r0, min(r0 + ROW_BLOCK, ny))
        ts = stack.read_cumulative(epochs, rows)
        v, s = resample_timeseries(
            ts,
            dates,
            np.array([target], dtype="datetime64[s]"),
            opts.window_days,
            opts.method,
            min_points=opts.min_points,
            max_extrapolation_days=opts.max_extrapolation_days,
        )
        s_cal = stack.read_calibration_std(nearest, rows)
        value[rows] = v[0]
        sigma[rows] = np.sqrt(s[0] ** 2 + s_cal**2)
    return value, sigma


# ------------------------------------------------------------------- GNSS
def load_gnss(workflow: Workflow, stacks: list[GeometryStack], grid: Grid):
    """GNSS E/N/U velocity field (mm/yr) on `grid`, verified against DISP-CAL."""
    from venti.gnss.sampling import GnssGridConfig
    from venti.gnss.vlm import (
        ProvenanceMismatchError,
        ProvenanceMissingError,
        load_gnss_for_vlm,
    )

    opts = workflow.algorithm_parameters.gnss_options
    inputs = workflow.input_file_group
    cal_products = [p.cal for s in stacks for p in s.pairs]
    exclude, db_version = None, None
    if opts.exclude_defo_nodes:
        exclude, db_version = _defo_areas(workflow)
    grid_cfg = None
    if inputs.unr_grid_latlon_file is not None and inputs.unr_timeseries_dir:
        grid_cfg = GnssGridConfig(
            grid_lookup=inputs.unr_grid_latlon_file,
            station_dir=inputs.unr_timeseries_dir,
            utm_epsg=grid.epsg,
            buffer_meters=opts.buffer_meters,
            exclude_defo_nodes=opts.exclude_defo_nodes,
            reinterpolate_excluded=opts.reinterpolate_excluded,
        )
    elif opts.horizontal_source == "grid" or not _has_gnss_layers(cal_products[0]):
        raise InputValidationError(
            "no GNSS horizontal field: give unr_grid_latlon_file and"
            " unr_timeseries_dir (the DISP-CAL products carry no gnss_ve/gnss_vn"
            f" layers, or horizontal_source is {opts.horizontal_source!r})",
            1003,
        )
    try:
        return load_gnss_for_vlm(
            cal_products,
            grid_cfg,  # type: ignore[arg-type]  # None only when the products carry layers
            (grid.x, grid.y),
            exclude=exclude,
            defo_db_version=db_version,
            allow_missing_provenance=not opts.require_provenance_match,
        )
    except (ProvenanceMismatchError, ProvenanceMissingError) as e:
        raise InputValidationError(str(e), 1003) from e


def _has_gnss_layers(cal_product: Path) -> bool:
    import h5py

    with h5py.File(cal_product, "r") as f:
        return "gnss_ve" in f and "gnss_vn" in f


def _defo_areas(workflow: Workflow) -> tuple[list, str | None]:
    """Deforming areas and the database version, read as DISP-CAL reads them.

    Venti's loader (`venti.calibration.remove_restore.load_area_db`) is the
    one cal-disp uses, so the version recorded in the DISP-CAL provenance
    (the database's top-level ``version``) and this one always agree.
    """
    from venti.calibration.remove_restore import load_area_db

    path = workflow.static_ancillary_file_group.defo_area_db_json
    if path is None:
        raise InputValidationError(
            "gnss_options.exclude_defo_nodes needs"
            " static_ancillary_file_group.defo_area_db_json",
            1003,
        )
    db = load_area_db(path)
    return db.shapes(), db.version


def context_layers(
    workflow: Workflow, coarse: Grid, grid: Grid
) -> tuple[dict[str, np.ndarray], dict[str, str]]:
    """Plate-motion and GIA rates (m/yr) on `grid`, and their identification."""
    from opera_vlm.context import frame_plate, gia_rate, plate_motion

    opts = workflow.algorithm_parameters.context_options
    plate = opts.plate or frame_plate(workflow.input_file_group.frame_id)
    ve, vn = plate_motion(coarse, plate, opts.plate_model)
    layers = {
        "plate_motion_east_rate": warp(ve, coarse, grid).astype(np.float32),
        "plate_motion_north_rate": warp(vn, coarse, grid).astype(np.float32),
    }
    ident = {"plate": plate, "plate_motion_model": opts.plate_model}
    gia = workflow.static_ancillary_file_group.gia_model_file
    if gia is not None:
        layers["gia_vertical_rate"] = warp(
            gia_rate(Path(gia), coarse, opts.gia_variable), coarse, grid
        ).astype(np.float32)
        ident["gia_model"] = Path(gia).name
    return layers, ident


# ------------------------------------------------------------- the run
def _ceos_runtime(
    stacks: list[GeometryStack], los: list[tuple[np.ndarray, ...]]
) -> dict[str, Any]:
    import h5py

    satellites: set[str] = set()
    for s in stacks:
        with h5py.File(s.pairs[0].disp, "r") as f:
            names = f.get("identification/source_data_satellite_names")
            if names is not None:
                value = names[()]
                text = value.decode() if isinstance(value, bytes) else str(value)
                satellites.update(t.strip() for t in text.split(",") if t.strip())
    inc = []
    for _, _, u in los:
        ok = np.isfinite(u)
        if ok.any():
            inc.append(np.degrees(np.arccos(np.clip(np.abs(u[ok]), 0, 1))))
    angles = np.concatenate(inc) if inc else np.array([np.nan])
    return {
        "source_data_satellite_names": ", ".join(sorted(satellites)) or "unknown",
        "orbit_pass_direction": ", ".join(s.name.capitalize() for s in stacks),
        "near_range_incidence_angle": float(np.nanmin(angles)),
        "far_range_incidence_angle": float(np.nanmax(angles)),
    }


def _stacks(workflow: Workflow) -> list[GeometryStack]:
    from venti.sensor import sensor_for_file

    inputs = workflow.input_file_group
    layer = sensor_for_file(inputs.ascending_disp_files[0]).displacement_layer
    masks = tuple(workflow.algorithm_parameters.input_options.mask_layers)
    stacks = [
        GeometryStack(
            inputs.ascending_disp_files,
            inputs.ascending_cal_files,
            displacement_layer=layer,
            mask_layers=masks,
            name="ascending",
        )
    ]
    if inputs.descending_disp_files:
        if workflow.dynamic_ancillary_file_group.los_file_descending is None:
            raise InputValidationError(
                "descending inputs need"
                " dynamic_ancillary_file_group.los_file_descending",
                1003,
            )
        stacks.append(
            GeometryStack(
                inputs.descending_disp_files,
                inputs.descending_cal_files,
                displacement_layer=layer,
                mask_layers=masks,
                name="descending",
            )
        )
    return stacks


def run_algorithm(workflow: Workflow) -> Iterator[AlgorithmResult]:
    """Yield one `AlgorithmResult` per target pair ``(T0, Tk)``."""
    from venti.decomposition import decompose
    from venti.gnss.vlm import pair_displacement

    params = workflow.algorithm_parameters
    logger.info("Algorithm parameters:\n%s", params.to_yaml_str())
    if workflow.output_options.get("write_velocity_product"):
        raise AlgorithmError(
            "output_options.write_velocity_product is not implemented yet (plan T56)"
        )
    dec = params.decomposition_options

    stacks = _stacks(workflow)
    grid = stacks[0].grid
    dyn = workflow.dynamic_ancillary_file_group
    los_files = [dyn.los_file_ascending, dyn.los_file_descending][: len(stacks)]
    los = [read_los(Path(p), grid) for p in los_files]  # type: ignore[arg-type]
    topts = params.temporal_options
    targets = target_epochs(
        stacks, topts.target_spacing_days, topts.window_days, topts.min_points
    )
    logger.info(
        "%s; %d target epochs %s .. %s every %g days",
        ", ".join(f"{s.name}: {len(s.pairs)} pairs" for s in stacks),
        len(targets),
        f"{targets[0]:%Y-%m-%d}",
        f"{targets[-1]:%Y-%m-%d}",
        params.temporal_options.target_spacing_days,
    )

    coarse = coarse_grid(grid, GNSS_POSTING_METERS)
    gnss = load_gnss(workflow, stacks, coarse)
    ceos = _ceos_runtime(stacks, los)
    context, context_id = context_layers(workflow, coarse, grid)
    sources = [f for s in stacks for f in s.source_files]
    at_t0 = [resample_at(s, targets[0], workflow) for s in stacks]

    for k, tk in enumerate(targets[1:], 1):
        logger.info("target pair %d/%d: %s", k, len(targets) - 1, f"{tk:%Y-%m-%d}")
        looks, sigmas = [], []
        for s, (v0, s0) in zip(stacks, at_t0, strict=True):
            d, sig = resample_at(s, tk, workflow)
            d -= v0  # in place: the pair R(Tk) - R(T0)
            span = (tk - targets[0]).days / 365.25
            np.sqrt(
                s0**2
                + sig**2
                + dec.sigma_disp_meters**2
                + (dec.sigma_rate_meters_per_year * span) ** 2,
                out=sig,
            )
            looks.append(d)
            sigmas.append(sig)
        g = pair_displacement(gnss, targets[0], tk)
        mm = 1e-3  # the UNR grid is in mm
        gnss_m = {
            "de": g["de"] * mm,
            "dn": g["dn"] * mm,
            "sde": np.nan_to_num(g["sigma_de"]) * mm,
            "sdn": np.nan_to_num(g["sigma_dn"]) * mm,
        }
        out = {
            name: np.full(grid.shape, np.nan, dtype=np.float32)
            for name in ("vertical", "vertical_std", "east", "east_std")
        }
        mode = np.zeros(grid.shape, dtype=np.uint8)
        # row blocks: the descending warp, the GNSS interpolation and the
        # decomposition never hold more than a block in float64
        for rows in row_blocks(grid.shape[0]):
            block = sub_grid(grid, rows)
            b_looks = [
                look[rows] if s.grid.same_as(grid) else warp(look, s.grid, block)
                for look, s in zip(looks, stacks, strict=True)
            ]
            b_sig = [
                sg[rows] if s.grid.same_as(grid) else warp(sg, s.grid, block)
                for sg, s in zip(sigmas, stacks, strict=True)
            ]
            b_gnss = {key: warp(v, coarse, block) for key, v in gnss_m.items()}
            res = decompose(
                b_looks,
                b_sig,
                [tuple(c[rows].astype(np.float64) for c in enu) for enu in los],
                b_gnss["de"],
                b_gnss["dn"],
                sigma_east_gnss=b_gnss["sde"],
                sigma_north_gnss=b_gnss["sdn"],
                cond_max=dec.cond_max,
                min_up=dec.min_up,
            )
            out["vertical"][rows] = res.up
            out["vertical_std"][rows] = res.sigma_up
            out["east"][rows] = res.east
            out["east_std"][rows] = res.sigma_east
            mode[rows] = res.mode
        del looks, sigmas
        counts = {
            "none": int((mode == 0).sum()),
            "wls": int((mode == 1).sum()),
            "projection": int((mode == 2).sum()),
        }
        logger.info("%s_%s: %s", f"{targets[0]:%Y%m%d}", f"{tk:%Y%m%d}", counts)
        layers = xr.Dataset(
            {
                **{name: (("y", "x"), v) for name, v in out.items()},
                "mode": (("y", "x"), mode),
                **{k: (("y", "x"), v) for k, v in context.items()},
            },
            coords={"x": grid.x, "y": grid.y},
            attrs={"epsg": grid.epsg},
        )
        yield AlgorithmResult(
            layers=layers,
            reference_datetime=targets[0],
            secondary_datetime=tk,
            source_files=sources,
            identification={
                "gnss_provenance_digest": gnss.provenance.digest,
                "number_of_looks": len(stacks),
                **context_id,
            },
            ceos=ceos,
        )
