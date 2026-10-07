# SPDX-FileCopyrightText: 2026 California Institute of Technology ("Caltech")
# SPDX-License-Identifier: Apache-2.0
# Part of opera-vlm, https://github.com/mgovorcin/opera-vlm.
"""Browse image (PNG quick-look) of the main product layer."""

from __future__ import annotations

from pathlib import Path

import numpy as np


def make_browse_image(
    product: Path, layer: str, output_png: Path, max_dim: int = 2048
) -> Path:
    """Write a downsampled PNG of `layer` (2-98 percentile stretch, NaN transparent)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import xarray as xr

    with xr.open_dataset(product, engine="h5netcdf") as ds:
        data = ds[layer].values
    step = max(1, int(np.ceil(max(data.shape) / max_dim)))
    data = data[::step, ::step]
    finite = data[np.isfinite(data)]
    vmin, vmax = np.percentile(finite, [2, 98]) if finite.size else (0.0, 1.0)
    plt.imsave(output_png, data, vmin=vmin, vmax=vmax, cmap="viridis")
    return output_png
