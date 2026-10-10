# SPDX-FileCopyrightText: 2026 California Institute of Technology ("Caltech")
# SPDX-License-Identifier: Apache-2.0
# Part of opera-vlm, https://github.com/mgovorcin/opera-vlm.
"""A synthetic ascending/descending frame with known east, north, up (plan T56.4).

Truth, in mm/yr on UTM coordinates:

- east and north: the long-wavelength planes of the UNR grid snapshot (the
  same planes the snapshot's nodes carry, so GNSS horizontal is exact);
- up: that grid's plane plus a 20 mm/yr subsidence bowl the grid does not
  see, so a correct vertical needs the InSAR.

DISP pairs carry the truth projected on a per-geometry LOS, a random
per-date ramp (the long-wavelength error) and small noise; DISP-CAL removes
exactly the ramp. The descending grid is shifted by half a pixel and a few
columns, so it must be resampled and its edge columns are single-look
(mode 2). Each stack has two reference blocks.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import h5py
import numpy as np
import rasterio
from affine import Affine
from pyproj import CRS, Transformer

EPSG = 32615
X0, Y0 = 250_000.0, 3_300_000.0  # upper-left corner of the ascending grid
LOS = {  # (east, north, up) ground-to-satellite unit vectors
    "ascending": (-0.62, -0.11, 0.777),
    "descending": (0.60, -0.12, 0.791),
}


@dataclass
class SyntheticFrame:
    """Paths of one synthetic frame and its truth functions."""

    root: Path
    asc_disp: list[Path]
    asc_cal: list[Path]
    desc_disp: list[Path]
    desc_cal: list[Path]
    los_asc: Path
    los_desc: Path
    lookup: Path
    station_dir: Path
    x: np.ndarray
    y: np.ndarray
    centre: tuple[float, float]
    size: float

    def velocity(self, x: np.ndarray, y: np.ndarray):
        """Truth east, north, up velocity (mm/yr) at UTM `x`, `y`."""
        ve, vn, vu = _plane(x, y, self.centre)
        r2 = ((x - self.centre[0]) ** 2 + (y - self.centre[1]) ** 2) / (
            0.15 * self.size
        ) ** 2
        return ve, vn, vu - 20.0 * np.exp(-r2)


def _plane(x, y, centre):
    dx = (x - centre[0]) / 1e5
    dy = (y - centre[1]) / 1e5
    return -12.0 + 3.0 * dx, -2.0 - 1.0 * dy, -3.0 + 2.0 * dx + 1.5 * dy


def _years(a: datetime, b: datetime) -> float:
    # the same decimal-year difference venti.gnss.vlm.pair_displacement uses
    def dec(d: datetime) -> float:
        d0, d1 = datetime(d.year, 1, 1), datetime(d.year + 1, 1, 1)
        return d.year + (d - d0).total_seconds() / (d1 - d0).total_seconds()

    return dec(b) - dec(a)


def _write_product(
    path: Path, x, y, layers: dict[str, np.ndarray], provenance: str | None = None
) -> None:
    with h5py.File(path, "w") as f:
        if provenance is not None:
            f["metadata/gnss_provenance"] = provenance
        f["x"] = x
        f["y"] = y
        ref = f.create_dataset("spatial_ref", data=0)
        ref.attrs["crs_wkt"] = CRS.from_epsg(EPSG).to_wkt()
        for k, v in layers.items():
            f[k] = v.astype(np.float32)
        f["identification/source_data_satellite_names"] = "S1A, S1B"


def _write_los(path: Path, x, y, enu, ny, nx) -> None:
    dx = float(x[1] - x[0])
    # a small range gradient so the incidence angles span a range
    ramp = np.linspace(-0.02, 0.02, nx)[None, :]
    e = np.full((ny, nx), enu[0]) + ramp * np.sign(enu[0])
    n = np.full((ny, nx), enu[1])
    u = np.sqrt(np.clip(1 - e**2 - n**2, 0, 1))
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=ny,
        width=nx,
        count=3,
        dtype="float32",
        crs=f"EPSG:{EPSG}",
        transform=Affine(dx, 0.0, x[0] - dx / 2, 0.0, -dx, y[0] + dx / 2),
    ) as ds:
        ds.write(np.stack([e, n, u]).astype(np.float32))


def _snapshot(root: Path, centre, size) -> tuple[Path, Path]:
    to_ll = Transformer.from_crs(f"EPSG:{EPSG}", "EPSG:4326", always_xy=True)
    step = max(size / 4, 2_000.0)
    xs = np.arange(X0 - 3 * step, X0 + size + 3 * step + 1, step)
    ys = np.arange(Y0 - size - 3 * step, Y0 + 3 * step + 1, step)
    xx, yy = (a.ravel() for a in np.meshgrid(xs, ys))
    ids = np.arange(1, xx.size + 1)
    lon, lat = to_ll.transform(xx, yy)
    lookup = root / "grid_latlon_lookup.txt"
    np.savetxt(lookup, np.c_[ids, lon, lat], fmt=["%06d", "%.8f", "%.8f"])
    station_dir = root / "unr_nodes"
    station_dir.mkdir()
    ve, vn, vu = _plane(xx, yy, centre)
    t = 2015 + np.arange(0, 12) * 0.5
    for i, node in enumerate(ids):
        rows = np.c_[
            t,
            ve[i] * (t - 2015),
            vn[i] * (t - 2015),
            vu[i] * (t - 2015),
            np.full_like(t, 0.4),
            np.full_like(t, 0.5),
            np.full_like(t, 1.2),
            np.zeros_like(t),
        ]
        np.savetxt(station_dir / f"{node:06d}_IGS20_constant.tenv8", rows, fmt="%.6f")
    return lookup, station_dir


def make_frame(
    root: Path,
    n: int = 32,
    posting: float = 600.0,
    n_epochs: int = 12,
    noise_m: float = 0.0005,
    seed: int = 0,
    buffer_meters: float | None = 50_000.0,
) -> SyntheticFrame:
    """Write a synthetic asc/desc frame of ``n x n`` pixels under `root`.

    DISP-CAL products carry the GNSS provenance record (plan T37.3) of the
    snapshot sampled with `buffer_meters`; None writes no record.
    """
    rng = np.random.default_rng(seed)
    root.mkdir(parents=True, exist_ok=True)
    size = n * posting
    centre = (X0 + size / 2, Y0 - size / 2)
    x_a = X0 + posting * (np.arange(n) + 0.5)
    y_a = Y0 - posting * (np.arange(n) + 0.5)
    shift = 3.5 * posting  # descending: shifted east by 3.5 pixels
    grids = {"ascending": (x_a, y_a), "descending": (x_a + shift, y_a)}
    starts = {"ascending": datetime(2020, 1, 1), "descending": datetime(2020, 1, 7)}
    out: dict[str, tuple[list[Path], list[Path]]] = {}
    frame = SyntheticFrame(
        root, [], [], [], [], root / "los_asc.tif", root / "los_desc.tif",
        *_snapshot(root, centre, size), x_a, y_a, centre, size,
    )  # fmt: skip
    provenance = None
    if buffer_meters is not None:
        import json

        from venti.gnss.sampling import GnssGridConfig, sample_gnss_enu

        cfg = GnssGridConfig(
            grid_lookup=frame.lookup,
            station_dir=frame.station_dir,
            utm_epsg=EPSG,
            buffer_meters=buffer_meters,
        )
        record = sample_gnss_enu(cfg, (x_a, y_a)).provenance.as_dict()
        provenance = json.dumps(record)
    for geom, (x, y) in grids.items():
        xx, yy = np.meshgrid(x, y)
        ve, vn, vu = frame.velocity(xx, yy)
        e, nn, u = LOS[geom]
        v_los = (e * ve + nn * vn + u * vu) / 1000.0  # m/yr
        dates = [starts[geom] + timedelta(days=12 * i) for i in range(n_epochs)]
        ramp = {d: rng.normal(0, 0.01) * (xx - centre[0]) / size for d in dates}
        ramp[dates[0]] = np.zeros_like(xx)
        half = n_epochs // 2
        blocks = [(dates[0], dates[1 : half + 1]), (dates[half], dates[half + 1 :])]
        disp, cal = [], []
        d = root / geom
        d.mkdir()
        for ref, secs in blocks:
            for sec in secs:
                tag = f"{ref:%Y%m%dT%H%M%S}Z_{sec:%Y%m%dT%H%M%S}Z"
                dramp = ramp[sec] - ramp[ref]
                signal = v_los * _years(ref, sec) + dramp
                signal += rng.normal(0, noise_m, signal.shape)
                p = d / f"OPERA_L3_DISP-S1_IW_F99999_VV_{tag}_v1.0_20261010T000000Z.nc"
                _write_product(p, x, y, {"displacement": signal})
                c = (
                    d
                    / f"OPERA_L4_DISP-CAL-S1_IW_F99999_VV_{tag}_v1.0_20261010T000000Z.nc"
                )
                _write_product(
                    c,
                    x,
                    y,
                    {
                        "calibration": dramp[None],
                        "calibration_std": np.full((1, n, n), 0.002),
                    },
                    provenance,
                )
                disp.append(p)
                cal.append(c)
        out[geom] = (disp, cal)
        _write_los(frame.los_asc if geom == "ascending" else frame.los_desc,
                   x, y, LOS[geom], n, n)  # fmt: skip
    frame.asc_disp, frame.asc_cal = out["ascending"]
    frame.desc_disp, frame.desc_cal = out["descending"]
    return frame


def runconfig_dict(frame: SyntheticFrame, tmp: Path, params: Path) -> dict:
    """A runconfig (as a dict) for `frame`."""
    return {
        "input_file_group": {
            "frame_id": 99999,
            "ascending_disp_files": [str(p) for p in frame.asc_disp],
            "ascending_cal_files": [str(p) for p in frame.asc_cal],
            "descending_disp_files": [str(p) for p in frame.desc_disp],
            "descending_cal_files": [str(p) for p in frame.desc_cal],
            "unr_grid_latlon_file": str(frame.lookup),
            "unr_timeseries_dir": str(frame.station_dir),
        },
        "dynamic_ancillary_file_group": {
            "algorithm_parameters_file": str(params),
            "los_file_ascending": str(frame.los_asc),
            "los_file_descending": str(frame.los_desc),
        },
        "product_path_group": {
            "product_path": str(tmp / "output"),
            "sas_output_path": str(tmp / "output"),
            "scratch_path": str(tmp / "scratch"),
        },
    }
