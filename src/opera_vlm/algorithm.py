# SPDX-FileCopyrightText: 2026 California Institute of Technology ("Caltech")
# SPDX-License-Identifier: Apache-2.0
# Part of opera-vlm, https://github.com/mgovorcin/opera-vlm.
"""The science algorithm.

`run_algorithm` receives the fully-resolved `Workflow` and returns the product
layers plus what the product writer needs for /identification. It must not
read YAML, apply defaults, or write the final product: config lives in
config/, product formatting in product/.

TODO(sas): replace the placeholder body. Until then every run logs a warning
and produces a constant placeholder product, which keeps the full chain
(config -> run -> product -> validate) testable from the first commit.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import xarray as xr

from opera_vlm._log import log_runtime
from opera_vlm.config import Workflow
from opera_vlm.product import LAYERS
from opera_vlm.product._ceos import CEOS_FIELDS, PLACEHOLDER

logger = logging.getLogger(__name__)

#: Set to False once run_algorithm is implemented.
IS_PLACEHOLDER = True


@dataclass
class AlgorithmResult:
    """Output of `run_algorithm`.

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


@log_runtime
def run_algorithm(workflow: Workflow) -> AlgorithmResult:
    """Run the algorithm for one job."""
    params = workflow.algorithm_parameters
    logger.info("Algorithm parameters:\n%s", params.to_yaml_str())

    # TODO(sas): replace from here -------------------------------------------
    logger.warning("PLACEHOLDER algorithm: the product contains no science")
    ny, nx, posting = 64, 64, 30.0
    x = 500_000.0 + posting * (np.arange(nx) + 0.5)
    y = 4_000_000.0 - posting * (np.arange(ny) + 0.5)
    layers = xr.Dataset(
        {
            spec.name: (("y", "x"), np.zeros((ny, nx), dtype=spec.dtype))
            for spec in LAYERS
        },
        coords={"x": x, "y": y},
        attrs={"epsg": 32611},
    )
    return AlgorithmResult(
        layers=layers,
        reference_datetime=datetime(2020, 1, 1),
        secondary_datetime=datetime(2020, 1, 13),
        source_files=[],
        # `opera-vlm ceos check` reports these as "placeholder" until real values
        ceos={f.name: PLACEHOLDER for f in CEOS_FIELDS if f.source == "runtime"},
    )
    # TODO(sas): ... to here --------------------------------------------------
