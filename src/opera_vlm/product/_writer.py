# SPDX-FileCopyrightText: 2026 California Institute of Technology ("Caltech")
# SPDX-License-Identifier: Apache-2.0
# Part of opera-vlm, https://github.com/mgovorcin/opera-vlm.
"""Write the output product: main layers, /identification, /metadata."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from opera_vlm.errors import ProductError

from ._layers import LAYERS, encoding, round_mantissa
from ._metadata import build_identification, build_metadata

if TYPE_CHECKING:
    from opera_vlm.algorithm import AlgorithmResult
    from opera_vlm.config import Workflow

logger = logging.getLogger(__name__)

EXTENSION = ".nc"


def product_filename(
    workflow: "Workflow", result: "AlgorithmResult", processing_start: datetime
) -> str:
    """OPERA-style file name, e.g.

    ``OPERA_<level>_<short name>_F<frame>_<start>_<end>_v<version>_<processing>.nc``
    """
    fmt = "%Y%m%dT%H%M%SZ"
    parts = ["OPERA", "L4", "VLM-S1"]
    if hasattr(workflow.input_file_group, "frame_id"):
        parts.append(f"F{int(workflow.input_file_group.frame_id):05d}")
    for dt in (result.reference_datetime, result.secondary_datetime):
        if dt is not None:
            parts.append(dt.strftime(fmt))
    parts.append("v" + workflow.output_options.get("product_version", "0.0"))
    parts.append(processing_start.strftime(fmt))
    return "_".join(parts) + EXTENSION


def write_product(
    workflow: "Workflow",
    result: "AlgorithmResult",
    pge_runconfig: str | None,
    processing_start: datetime,
) -> Path:
    """Write the product and return its path."""
    ds = result.layers.copy()
    missing = [s.name for s in LAYERS if s.name not in ds]
    if missing:
        raise ProductError(f"Algorithm did not produce layers: {missing}")
    for spec in LAYERS:
        da = ds[spec.name].astype(spec.dtype)
        if spec.keep_bits is not None:
            da = da.copy(data=round_mantissa(da.values, spec.keep_bits))
        ds[spec.name] = da.assign_attrs(spec.attrs())
    ds.attrs.update(
        Conventions="CF-1.8",
        title="OPERA VLM-S1 product",
        institution="NASA Jet Propulsion Laboratory (JPL)",
        source="OPERA Vertical Land Motion from DISP and DISP-CAL",
        contact="opera-sds-ops@jpl.nasa.gov",
        product_version=workflow.output_options.get("product_version", ""),
    )

    compression = bool(workflow.output_options.get("compression", True))
    ny, nx = ds.sizes.get("y", 1), ds.sizes.get("x", 1)
    chunks = (min(256, ny), min(256, nx))
    out = workflow.output_directory / product_filename(
        workflow, result, processing_start
    )
    try:
        ds.to_netcdf(
            out, engine="h5netcdf", mode="w", encoding=encoding(compression, chunks)
        )
        build_identification(workflow, result, processing_start).to_netcdf(
            out, group="identification", engine="h5netcdf", mode="a"
        )
        build_metadata(workflow, result, pge_runconfig).to_netcdf(
            out, group="metadata", engine="h5netcdf", mode="a"
        )
    except Exception as e:
        out.unlink(missing_ok=True)  # never leave a half-written product
        raise ProductError(f"Failed to write {out}: {e}") from e
    logger.info("Wrote %s", out)
    return out
