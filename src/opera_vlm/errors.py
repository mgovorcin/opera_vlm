# SPDX-FileCopyrightText: 2026 California Institute of Technology ("Caltech")
# SPDX-License-Identifier: Apache-2.0
# Part of opera-vlm, https://github.com/mgovorcin/opera-vlm.
"""Errors with stable exit codes and numbered input-validation codes.

The PGE maps the process exit code to a job status, and operators grep the log
for ``[error NNNN]``. Both are part of the interface: add codes, never reuse
or renumber them, and document each one in docs/error-codes.md
(tests/test_errors.py checks that every code is documented).
"""

from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    """Process exit codes of ``opera-vlm run``."""

    SUCCESS = 0
    UNEXPECTED_ERROR = 1
    USAGE_ERROR = 2  # click's own code for bad command-line arguments
    RUNCONFIG_ERROR = 3  # runconfig YAML unreadable or fails schema validation
    INPUT_VALIDATION_ERROR = 4  # inputs missing / inconsistent (prechecks)
    ALGORITHM_ERROR = 5  # processing failed
    PRODUCT_ERROR = 6  # writing or checking the output product failed


#: Numbered input-validation errors: code -> short description.
ERROR_CODES: dict[int, str] = {
    1000: "Required input file or directory does not exist.",
    1001: (
        "Input path has the wrong kind (file given where a directory is expected, or"
        " vice versa)."
    ),
    1002: "Algorithm parameters file or overrides are invalid.",
    1003: "Inputs are inconsistent with each other (e.g. different frames or dates).",
}


class SasError(Exception):
    """Base class: an expected failure with a known exit code."""

    exit_code: ExitCode = ExitCode.UNEXPECTED_ERROR


class RunConfigError(SasError):
    """The runconfig cannot be read or does not validate."""

    exit_code = ExitCode.RUNCONFIG_ERROR


class InputValidationError(SasError, ValueError):
    """An input precheck failed; carries a numbered error code."""

    exit_code = ExitCode.INPUT_VALIDATION_ERROR

    def __init__(self, message: str, error_code: int) -> None:
        if error_code not in ERROR_CODES:
            raise ValueError(f"Undocumented error code {error_code}")
        self.error_code = error_code
        super().__init__(f"[error {error_code}] {message}")


class AlgorithmError(SasError):
    """Processing failed for a reason the algorithm detected."""

    exit_code = ExitCode.ALGORITHM_ERROR


class ProductError(SasError):
    """Writing or verifying the output product failed."""

    exit_code = ExitCode.PRODUCT_ERROR
