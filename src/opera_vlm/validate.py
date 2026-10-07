# SPDX-FileCopyrightText: 2026 California Institute of Technology ("Caltech")
# SPDX-License-Identifier: Apache-2.0
# Part of opera-vlm, https://github.com/mgovorcin/opera-vlm.
"""Compare a test product against a golden product.

Used by ``opera-vlm validate`` and scripts/run_validation.sh. Structure must match
exactly (groups, variables, shapes, dtypes, attributes); values must match to
a tolerance. Fields that legitimately differ between runs (processing time,
software versions, paths in the embedded runconfig) are listed in VOLATILE.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import h5py
import numpy as np

logger = logging.getLogger(__name__)

#: Dataset/attribute paths whose values are not compared (structure still is).
VOLATILE = frozenset(
    {
        "identification/processing_start_datetime",
        "metadata/opera_vlm_software_version",
        "metadata/software_dependency_versions",
        "metadata/pge_runconfig",
        "metadata/resolved_workflow_yaml",
    }
)


@dataclass
class ValidationReport:
    """Collected failures and warnings of one comparison."""

    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """True when there are no failures."""
        return not self.failures

    def log(self) -> None:
        """Log the report."""
        for w in self.warnings:
            logger.warning(w)
        for f in self.failures:
            logger.error(f)
        logger.info(
            "Validation %s (%d failures)",
            "PASSED" if self.passed else "FAILED",
            len(self.failures),
        )


def _collect(h5: h5py.File) -> dict[str, h5py.Dataset]:
    items: dict[str, h5py.Dataset] = {}
    h5.visititems(
        lambda name, obj: (
            items.__setitem__(name, obj) if isinstance(obj, h5py.Dataset) else None
        )
    )
    return items


def _equal_attr(a, b) -> bool:
    a, b = np.asarray(a), np.asarray(b)
    try:
        return bool(np.array_equal(a, b, equal_nan=True))  # _FillValue = NaN
    except TypeError:  # strings / objects
        return bool(np.array_equal(a, b))


def compare_products(
    golden: Path | str, test: Path | str, rtol: float = 1e-5, atol: float = 1e-6
) -> ValidationReport:
    """Compare `test` to `golden` and return the report."""
    report = ValidationReport()
    with h5py.File(golden, "r") as g, h5py.File(test, "r") as t:
        gd, td = _collect(g), _collect(t)
        for name in sorted(set(gd) - set(td)):
            report.failures.append(f"missing in test: {name}")
        for name in sorted(set(td) - set(gd)):
            report.failures.append(f"extra in test: {name}")
        for name in sorted(set(gd) & set(td)):
            a, b = gd[name], td[name]
            if a.shape != b.shape:
                report.failures.append(f"{name}: shape {b.shape} != golden {a.shape}")
                continue
            if a.dtype != b.dtype:
                report.failures.append(f"{name}: dtype {b.dtype} != golden {a.dtype}")
            for key in set(a.attrs) | set(b.attrs):
                if key in ("DIMENSION_LIST", "REFERENCE_LIST"):
                    continue
                if key not in a.attrs or key not in b.attrs:
                    report.failures.append(
                        f"{name}: attribute {key!r} only in one product"
                    )
                elif not _equal_attr(a.attrs[key], b.attrs[key]):
                    report.failures.append(f"{name}: attribute {key!r} differs")
            if name in VOLATILE:
                continue
            va, vb = a[()], b[()]
            if np.issubdtype(np.asarray(va).dtype, np.number):
                if not np.allclose(va, vb, rtol=rtol, atol=atol, equal_nan=True):
                    diff = np.nanmax(
                        np.abs(np.asarray(va, float) - np.asarray(vb, float))
                    )
                    report.failures.append(
                        f"{name}: values differ (max |diff| {diff:.3g})"
                    )
            elif not np.array_equal(np.asarray(va), np.asarray(vb)):
                report.failures.append(f"{name}: values differ")
    return report
