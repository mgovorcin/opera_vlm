# SPDX-FileCopyrightText: 2026 California Institute of Technology ("Caltech")
# SPDX-License-Identifier: Apache-2.0
# Part of opera-vlm, https://github.com/mgovorcin/opera-vlm.
"""Product layer specification: one `LayerSpec` per output variable.

This table is the product spec in code. Keep it in sync with the product
specification document (docs/product-spec.md); tests check that every layer
is written with these attributes and dtypes.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class LayerSpec:
    """Specification of one product layer."""

    name: str
    dtype: str
    units: str
    description: str
    long_name: str
    #: Mantissa bits kept for lossy float compression (None = lossless).
    keep_bits: int | None = None
    fill_value: float | int = float("nan")
    #: False for context layers that are written only when their input is given.
    required: bool = True

    def attrs(self) -> dict[str, str]:
        """CF attributes of the layer."""
        return {
            "units": self.units,
            "long_name": self.long_name,
            "description": self.description,
        }


LAYERS: list[LayerSpec] = [
    LayerSpec(
        name="vertical",
        dtype="float32",
        units="meters",
        description=(
            "Vertical displacement of the pair (up positive), absolute in IGS20 after "
            "DISP-CAL."
        ),
        long_name="vertical",
        keep_bits=12,
        fill_value=float("nan"),
    ),
    LayerSpec(
        name="vertical_std",
        dtype="float32",
        units="meters",
        description=(
            "1-sigma of vertical, propagated from sigma_CAL, sigma_DISP, the GNSS "
            "horizontal sigmas and the temporal resampling."
        ),
        long_name="vertical std",
        keep_bits=10,
        fill_value=float("nan"),
    ),
    LayerSpec(
        name="east",
        dtype="float32",
        units="meters",
        description=(
            "East displacement where ascending and descending overlap (mode 1); NaN "
            "elsewhere."
        ),
        long_name="east",
        keep_bits=12,
        fill_value=float("nan"),
    ),
    LayerSpec(
        name="east_std",
        dtype="float32",
        units="meters",
        description="1-sigma of east.",
        long_name="east std",
        keep_bits=10,
        fill_value=float("nan"),
    ),
    LayerSpec(
        name="mode",
        dtype="uint8",
        units="unitless",
        description=(
            "0 no data, 1 asc+desc WLS with north from GNSS, 2 single-geometry "
            "projection with east and north from GNSS (valid for long-wavelength "
            "horizontal motion only)."
        ),
        long_name="mode",
        keep_bits=None,
        fill_value=255,
    ),
    LayerSpec(
        name="plate_motion_east_rate",
        dtype="float32",
        units="meters / year",
        description=(
            "Context: east velocity of the frame's rigid plate (ITRF2020-PMM). East "
            "minus this rate times the pair's span is plate-fixed. Not removed."
        ),
        long_name="plate motion east rate",
        keep_bits=12,
        required=False,
    ),
    LayerSpec(
        name="plate_motion_north_rate",
        dtype="float32",
        units="meters / year",
        description="Context: north velocity of the frame's rigid plate. Not removed.",
        long_name="plate motion north rate",
        keep_bits=12,
        required=False,
    ),
    LayerSpec(
        name="gia_vertical_rate",
        dtype="float32",
        units="meters / year",
        description=(
            "Context: vertical rate of the GIA model (ICE-6G_D), when one is given. "
            "Not removed."
        ),
        long_name="GIA vertical rate",
        keep_bits=12,
        required=False,
    ),
]


def round_mantissa(data: np.ndarray, keep_bits: int) -> np.ndarray:
    """Zero all but `keep_bits` mantissa bits of a float32 array (round-to-nearest).

    Makes gzip far more effective at a bounded relative error of
    2**-(keep_bits + 1). Non-finite values are left untouched.
    """
    if data.dtype != np.float32:
        raise TypeError(f"round_mantissa needs float32, got {data.dtype}")
    drop = 23 - keep_bits
    if drop <= 0:
        return data
    out = data.copy()
    finite = np.isfinite(out)
    bits = out.view(np.uint32)
    half = np.uint32((1 << (drop - 1)) - 1)
    lsb = (bits >> np.uint32(drop)) & np.uint32(1)
    rounded = (bits + half + lsb) & ~np.uint32((1 << drop) - 1)
    bits[finite] = rounded[finite]
    return out


def encoding(
    compression: bool,
    chunks: tuple[int, int] = (256, 256),
    names: set[str] | None = None,
) -> dict:
    """xarray/h5netcdf encoding for every layer (or only those in `names`)."""
    enc: dict = {}
    for spec in LAYERS:
        if names is not None and spec.name not in names:
            continue
        e: dict = {"dtype": spec.dtype, "_FillValue": spec.fill_value}
        if compression:
            e.update(compression="gzip", compression_opts=4, shuffle=True)
            e["chunksizes"] = chunks
        enc[spec.name] = e
    return enc
