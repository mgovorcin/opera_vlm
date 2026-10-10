# SPDX-FileCopyrightText: 2026 California Institute of Technology ("Caltech")
# SPDX-License-Identifier: Apache-2.0
# Part of opera-vlm, https://github.com/mgovorcin/opera-vlm.
"""One look geometry: DISP pairs, their DISP-CAL products, chained epochs.

A DISP stack is a set of pairs that share a reference date within a block
(``ref -> sec``); a new block starts on a later secondary date. The
calibrated displacement of a pair is ``DISP - calibration`` (absolute after
DISP-CAL), and the cumulative series is chained across blocks:
``cum(sec) = cum(ref) + pair(ref, sec)`` with ``cum(first reference) = 0``.

Rows are read on demand (`read_cumulative`), so a full frame never has to
fit in memory: a VLM target needs only the epochs inside its window plus
the block-boundary pairs of the chain.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import h5py
import numpy as np

from opera_vlm.errors import InputValidationError

#: The two datetimes of an OPERA DISP / DISP-CAL file name.
_DATES = re.compile(r"_(\d{8}T\d{6})Z?_(\d{8}T\d{6})Z?_")
_FMT = "%Y%m%dT%H%M%S"


def pair_dates(path: Path | str) -> tuple[datetime, datetime]:
    """Return the reference and secondary datetimes of an OPERA DISP/DISP-CAL name."""
    m = _DATES.search(Path(path).name)
    if m is None:
        raise InputValidationError(
            f"{Path(path).name}: no <reference>_<secondary> dates in the name", 1003
        )
    return datetime.strptime(m.group(1), _FMT), datetime.strptime(m.group(2), _FMT)


@dataclass(frozen=True)
class Pair:
    """One DISP product and its DISP-CAL product."""

    disp: Path
    cal: Path
    reference: datetime
    secondary: datetime


@dataclass(frozen=True)
class Grid:
    """A north-up UTM grid: pixel-centre coordinates and the EPSG code."""

    x: np.ndarray
    y: np.ndarray
    epsg: int

    @property
    def shape(self) -> tuple[int, int]:
        """``(ny, nx)``."""
        return self.y.size, self.x.size

    @property
    def transform(self):  # -> affine.Affine
        """Affine transform of the pixel corners."""
        from affine import Affine

        # built directly: rasterio's from_origin warns under affine 3
        dx = float(self.x[1] - self.x[0])
        dy = float(self.y[0] - self.y[1])
        return Affine(dx, 0.0, self.x[0] - dx / 2, 0.0, -dy, self.y[0] + dy / 2)

    @classmethod
    def from_product(cls, path: Path | str) -> "Grid":
        """Grid of an OPERA DISP / DISP-CAL product (``x``, ``y``, ``spatial_ref``)."""
        from pyproj import CRS

        with h5py.File(path, "r") as f:
            x, y = f["x"][()], f["y"][()]
            ref = f["spatial_ref"]
            wkt = ref.attrs.get("crs_wkt")
            if wkt is not None:
                epsg = CRS.from_wkt(_text(wkt)).to_epsg()
            else:
                epsg = int(ref[()])
        if epsg is None:
            raise InputValidationError(f"{Path(path).name}: CRS has no EPSG code", 1003)
        return cls(x=np.asarray(x, float), y=np.asarray(y, float), epsg=int(epsg))

    def same_as(self, other: "Grid") -> bool:
        """Return True when both grids are identical (no resampling needed)."""
        return (
            self.epsg == other.epsg
            and self.shape == other.shape
            and np.allclose(self.x, other.x)
            and np.allclose(self.y, other.y)
        )


def _text(value: object) -> str:
    return value.decode() if isinstance(value, bytes) else str(value)


class GeometryStack:
    """Calibrated, chained displacement of one look geometry.

    Parameters
    ----------
    disp_files, cal_files : list of path
        DISP products and the DISP-CAL product of each (matched on the
        reference and secondary dates).
    displacement_layer : str
        DISP dataset name (``SensorSpec.displacement_layer``).
    name : str
        ``"ascending"`` or ``"descending"``, for messages.

    Raises
    ------
    InputValidationError
        A DISP product without a DISP-CAL product (1003), duplicate pairs,
        a block reference that is not a secondary of an earlier pair, or
        products on different grids.

    """

    def __init__(
        self,
        disp_files: list[Path],
        cal_files: list[Path],
        *,
        displacement_layer: str = "displacement",
        name: str = "ascending",
    ) -> None:
        self.name = name
        self.displacement_layer = displacement_layer
        cal_by_dates: dict[tuple[datetime, datetime], Path] = {}
        for c in cal_files:
            cal_by_dates[pair_dates(c)] = Path(c)
        pairs: dict[tuple[datetime, datetime], Pair] = {}
        missing = []
        for d in disp_files:
            key = pair_dates(d)
            if key in pairs:
                raise InputValidationError(
                    f"{name}: two DISP products for {key[0]:%Y%m%d}_{key[1]:%Y%m%d}",
                    1003,
                )
            if key not in cal_by_dates:
                missing.append(Path(d).name)
                continue
            pairs[key] = Pair(Path(d), cal_by_dates[key], *key)
        if missing:
            raise InputValidationError(
                f"{name}: no DISP-CAL product for {len(missing)} DISP product(s),"
                f" e.g. {missing[0]}",
                1003,
            )
        if not pairs:
            raise InputValidationError(f"{name}: no DISP products", 1003)
        self.pairs = sorted(pairs.values(), key=lambda p: (p.secondary, p.reference))
        self.origin = min(p.reference for p in self.pairs)
        by_secondary = {p.secondary: p for p in self.pairs}
        # each block reference must be reachable through earlier pairs
        self._chain: dict[datetime, list[Pair]] = {self.origin: []}
        for ref in sorted({p.reference for p in self.pairs}):
            if ref == self.origin:
                continue
            if ref not in by_secondary:
                raise InputValidationError(
                    f"{name}: block reference {ref:%Y-%m-%d} is not the secondary"
                    " date of any earlier pair; the stack cannot be chained",
                    1003,
                )
            link = by_secondary[ref]
            self._chain[ref] = [*self._chain[link.reference], link]
        self._by_secondary = by_secondary
        self.grid = Grid.from_product(self.pairs[0].disp)

    @property
    def dates(self) -> np.ndarray:
        """Epochs of the cumulative series: the origin, then every secondary."""
        return np.array([self.origin, *self._by_secondary], dtype="datetime64[s]")

    @property
    def source_files(self) -> list[str]:
        """DISP and DISP-CAL file names."""
        return [p.disp.name for p in self.pairs] + [p.cal.name for p in self.pairs]

    def _pair_rows(self, pair: Pair, rows: slice) -> np.ndarray:
        with h5py.File(pair.disp, "r") as f:
            disp = f[self.displacement_layer][rows, :].astype(np.float64)
        with h5py.File(pair.cal, "r") as f:
            cal = f["calibration"]
            cal = cal[0, rows, :] if cal.ndim == 3 else cal[rows, :]
        return disp - cal

    def read_cumulative(self, epochs: list[datetime], rows: slice) -> np.ndarray:
        """Cumulative calibrated displacement (meters) at `epochs` for `rows`.

        Returns ``(len(epochs), nrows, nx)``; NaN where any pair in the
        chain is NaN.
        """
        ny, nx = self.grid.shape
        nrows = len(range(*rows.indices(ny)))
        cache: dict[Path, np.ndarray] = {}

        def pair(p: Pair) -> np.ndarray:
            if p.disp not in cache:
                cache[p.disp] = self._pair_rows(p, rows)
            return cache[p.disp]

        out = np.empty((len(epochs), nrows, nx))
        for k, t in enumerate(epochs):
            if t == self.origin:
                out[k] = 0.0
                continue
            last = self._by_secondary[t]
            acc = pair(last).copy()
            for link in self._chain[last.reference]:
                acc += pair(link)
            out[k] = acc
        return out

    def read_calibration_std(self, epoch: datetime, rows: slice) -> np.ndarray:
        """``calibration_std`` (meters) of the pair ending at `epoch`."""
        if epoch == self.origin:
            ny, nx = self.grid.shape
            return np.zeros((len(range(*rows.indices(ny))), nx))
        with h5py.File(self._by_secondary[epoch].cal, "r") as f:
            if "calibration_std" not in f:
                ny, nx = self.grid.shape
                return np.zeros((len(range(*rows.indices(ny))), nx))
            s = f["calibration_std"]
            return (s[0, rows, :] if s.ndim == 3 else s[rows, :]).astype(np.float64)

    def epochs_within(self, t0: datetime, half_window_days: float) -> list[datetime]:
        """Epochs of the series with ``|t - t0| <= half_window_days``."""
        out = []
        for t in [self.origin, *self._by_secondary]:
            if abs((t - t0).total_seconds()) <= half_window_days * 86400.0:
                out.append(t)
        return out

    def nearest_epoch(self, t0: datetime) -> datetime:
        """Return the epoch of the series closest to `t0`."""
        return min(
            [self.origin, *self._by_secondary],
            key=lambda t: abs((t - t0).total_seconds()),
        )
