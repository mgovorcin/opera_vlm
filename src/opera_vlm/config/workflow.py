# SPDX-FileCopyrightText: 2026 California Institute of Technology ("Caltech")
# SPDX-License-Identifier: Apache-2.0
# Part of opera-vlm, https://github.com/mgovorcin/opera-vlm.
"""The internal, fully-resolved workflow configuration.

Built only by `RunConfig.to_workflow` (or directly in tests/notebooks). Paths
are absolute, algorithm overrides are applied: processing code reads this
object and nothing else, so the PGE contract can evolve independently.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field

from ._algorithm import AlgorithmParameters
from ._groups import DynamicAncillaryFileGroup, InputFileGroup, StaticAncillaryFileGroup
from ._workers import WorkerSettings
from ._yaml import STRICT_CONFIG, YamlModel


class Workflow(YamlModel):
    """Resolved configuration of one SAS run."""

    input_file_group: InputFileGroup
    dynamic_ancillary_file_group: DynamicAncillaryFileGroup
    static_ancillary_file_group: StaticAncillaryFileGroup
    algorithm_parameters: AlgorithmParameters = Field(
        default_factory=AlgorithmParameters
    )
    applied_overrides: dict[str, Any] = Field(default_factory=dict)
    work_directory: Path = Path("scratch")
    output_directory: Path = Path("output")
    keep_scratch: bool = False
    output_options: dict[str, Any] = Field(default_factory=dict)
    worker_settings: WorkerSettings = Field(default_factory=WorkerSettings)
    log_file: Path | None = None

    model_config = STRICT_CONFIG

    def create_directories(self) -> None:
        """Create the scratch and output directories."""
        self.work_directory.mkdir(parents=True, exist_ok=True)
        self.output_directory.mkdir(parents=True, exist_ok=True)
