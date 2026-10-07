# SPDX-FileCopyrightText: 2026 California Institute of Technology ("Caltech")
# SPDX-License-Identifier: Apache-2.0
# Part of opera-vlm, https://github.com/mgovorcin/opera-vlm.
"""CPU / threading settings of one run."""

from __future__ import annotations

import os
from typing import Tuple

from pydantic import Field, field_validator

from ._yaml import STRICT_CONFIG, YamlModel

#: Thread-count variables read by BLAS/OpenMP/numexpr/GDAL at import time.
THREAD_ENV_VARS = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "GDAL_NUM_THREADS",
)


class WorkerSettings(YamlModel):
    """Settings for controlling CPU/threading and block processing."""

    n_workers: int = Field(
        default=1,
        ge=1,
        le=256,
        description="Number of worker processes (or dask workers) to use.",
    )
    threads_per_worker: int = Field(
        default=4,
        ge=1,
        le=256,
        description="Threads per worker, exported to OMP/BLAS/GDAL thread variables.",
    )
    block_shape: Tuple[int, int] = Field(
        default=(512, 512),
        description="Size (rows, columns) of blocks of data to load at a time.",
    )

    model_config = STRICT_CONFIG

    @field_validator("block_shape", mode="before")
    @classmethod
    def _positive_block(cls, v):
        v = tuple(v)
        if len(v) != 2 or not all(isinstance(x, int) and x > 0 for x in v):
            raise ValueError(f"block_shape must be 2 positive integers, got {v}")
        return v

    @property
    def total_threads(self) -> int:
        """n_workers * threads_per_worker."""
        return self.n_workers * self.threads_per_worker

    def apply_thread_env(self) -> None:
        """Export the thread count, unless the environment already sets it.

        Call before numpy/GDAL are imported (the CLI does): libraries read
        these variables once, at import.
        """
        for var in THREAD_ENV_VARS:
            os.environ.setdefault(var, str(self.threads_per_worker))
