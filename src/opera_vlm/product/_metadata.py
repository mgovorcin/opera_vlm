# SPDX-FileCopyrightText: 2026 California Institute of Technology ("Caltech")
# SPDX-License-Identifier: Apache-2.0
# Part of opera-vlm, https://github.com/mgovorcin/opera-vlm.
"""/identification and /metadata groups: provenance of every product."""

from __future__ import annotations

import json
import platform
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING, Any

import xarray as xr

if TYPE_CHECKING:
    from opera_vlm.algorithm import AlgorithmResult
    from opera_vlm.config import Workflow


def iso_utc(dt: datetime | None) -> str:
    """ISO 8601 UTC with a ``Z`` suffix; naive datetimes are taken as UTC."""
    if dt is None:
        return ""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _scalar(value: Any, description: str) -> xr.DataArray:
    if isinstance(value, (list, tuple)):
        value = ", ".join(map(str, value))
    return xr.DataArray(value, attrs={"description": description})


def build_identification(
    workflow: "Workflow", result: "AlgorithmResult", processing_start: datetime
) -> xr.Dataset:
    """Scalar product identification (searchable metadata)."""
    out = workflow.output_options
    inputs = workflow.input_file_group
    data = {
        "product_type": _scalar("VLM", "Product type."),
        "product_version": _scalar(out.get("product_version", ""), "Product version."),
        "reference_datetime": _scalar(
            iso_utc(result.reference_datetime), "Start of the time span (UTC)."
        ),
        "secondary_datetime": _scalar(
            iso_utc(result.secondary_datetime), "End of the time span (UTC)."
        ),
        "processing_start_datetime": _scalar(
            iso_utc(processing_start), "Processing start (UTC)."
        ),
        "processing_facility": _scalar(
            out.get("processing_facility", ""), "Processing facility."
        ),
        "product_data_access": _scalar(
            out.get("product_data_access", ""), "Where this product can be retrieved."
        ),
        "source_data_file_list": _scalar(result.source_files, "Input granules."),
    }
    if hasattr(inputs, "frame_id"):
        data["frame_id"] = _scalar(int(inputs.frame_id), "Frame identifier.")
    for key, value in result.identification.items():
        data[key] = _scalar(value, key.replace("_", " ").capitalize() + ".")
    data.update(_ceos_group(result, "identification"))
    return xr.Dataset(data)


def _ceos_group(result: "AlgorithmResult", group: str) -> dict:
    from ._ceos import CEOS_FIELDS, ceos_values

    describe = {f.name: f"{f.description} (CEOS-ARD {f.section})" for f in CEOS_FIELDS}
    return {
        name: _scalar(value, describe[name])
        for name, value in ceos_values(result)[group].items()
    }


def _dependency_versions() -> dict[str, str]:
    from opera_vlm._log import KEY_DEPENDENCIES

    versions = {"python": platform.python_version()}
    for dist in KEY_DEPENDENCIES:
        try:
            versions[dist] = version(dist)
        except PackageNotFoundError:
            pass
    return versions


def build_metadata(
    workflow: "Workflow", result: "AlgorithmResult", pge_runconfig: str | None
) -> xr.Dataset:
    """Everything needed to reproduce the product."""
    from io import StringIO

    from opera_vlm._version import __version__

    buf = StringIO()
    workflow.to_yaml(buf, with_comments=False)
    return xr.Dataset(
        {
            "opera_vlm_software_version": _scalar(__version__, "SAS software version."),
            "software_dependency_versions": _scalar(
                json.dumps(_dependency_versions()),
                "Versions of key dependencies (JSON).",
            ),
            "algorithm_parameters_yaml": _scalar(
                workflow.algorithm_parameters.to_yaml_str(),
                "Algorithm parameters used, after overrides (YAML).",
            ),
            "algorithm_parameters_overrides": _scalar(
                json.dumps(workflow.applied_overrides),
                "Overrides applied for this job (JSON).",
            ),
            "pge_runconfig": _scalar(
                pge_runconfig or "", "PGE runconfig as run (YAML)."
            ),
            "resolved_workflow_yaml": _scalar(
                buf.getvalue(), "Resolved internal workflow (YAML)."
            ),
            **_ceos_group(result, "metadata"),
        }
    )
