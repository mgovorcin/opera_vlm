# SPDX-FileCopyrightText: 2026 California Institute of Technology ("Caltech")
# SPDX-License-Identifier: Apache-2.0
# Part of opera-vlm, https://github.com/mgovorcin/opera-vlm.
"""Staging (download) functions; network dependencies are imported lazily."""

from ._sources import stage_cal, stage_disp, stage_unr

__all__ = ["stage_disp", "stage_cal", "stage_unr"]
