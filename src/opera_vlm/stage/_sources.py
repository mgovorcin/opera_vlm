# SPDX-FileCopyrightText: 2026 California Institute of Technology ("Caltech")
# SPDX-License-Identifier: Apache-2.0
# Part of opera-vlm, https://github.com/mgovorcin/opera-vlm.
"""One function per staging source.

GENERATED stubs. Conventions:
- Return the list of local paths written (so they can be fed to `config runconfig`).
- Skip files that already exist with the right size (idempotent re-runs).
- Credentials from ~/.netrc (Earthdata) or the AWS profile, never from arguments.
- Retry transient network errors (e.g. tenacity or urllib3 Retry).
"""

from __future__ import annotations

from pathlib import Path


def stage_disp(output_dir: Path, frame_id: int) -> list[Path]:
    """Download DISP-S1 products for a frame and date range.

    Returns the local paths written, so `stage all` can build a runconfig.
    """
    # TODO(sas): implement. Source: ASF DAAC (opera-utils)
    raise NotImplementedError("stage disp is not implemented yet")


def stage_cal(output_dir: Path, frame_id: int) -> list[Path]:
    """Download the DISP-CAL products matching staged DISP products.

    Returns the local paths written, so `stage all` can build a runconfig.
    """
    # TODO(sas): implement. Source: ASF DAAC
    raise NotImplementedError("stage cal is not implemented yet")


def stage_unr(output_dir: Path, frame_id: int) -> list[Path]:
    """Fetch a frozen UNR grid snapshot (Venti plan T48).

    Returns the local paths written, so `stage all` can build a runconfig.
    """
    # TODO(sas): implement. Source: s3://opera-adt/opera-ancillary/unr-grid
    raise NotImplementedError("stage unr is not implemented yet")
