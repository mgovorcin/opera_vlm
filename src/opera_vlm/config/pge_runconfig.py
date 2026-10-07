# SPDX-FileCopyrightText: 2026 California Institute of Technology ("Caltech")
# SPDX-License-Identifier: Apache-2.0
# Part of opera-vlm, https://github.com/mgovorcin/opera-vlm.
"""PGE runconfig: the YAML contract between the PGE and this SAS.

Keep this file boring and stable: the PGE team generates these YAMLs. Science
knobs belong in the algorithm parameters (config/_algorithm.py), not here.
`RunConfig.to_workflow` turns this contract into the fully-resolved internal
`Workflow` (absolute paths, algorithm parameters loaded and overridden), so
the processing code never reads YAML or applies defaults itself.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import ClassVar, Final, Literal, Optional

from pydantic import Field, ValidationError

from opera_vlm.errors import InputValidationError, RunConfigError

from ._algorithm import AlgorithmParameters
from ._groups import DynamicAncillaryFileGroup, InputFileGroup, StaticAncillaryFileGroup
from ._utils import DirectoryPath, read_overrides
from ._workers import WorkerSettings
from ._yaml import STRICT_CONFIG_WITH_ALIASES, YamlModel
from .workflow import Workflow

logger = logging.getLogger(__name__)

PRODUCT_TYPE: Final = "VLM"

#: (group attribute, field, "file"|"dir") of every path input; generated.
PATH_INPUTS: tuple[tuple[str, str, str], ...] = (
    ("dynamic_ancillary_file_group", "algorithm_parameters_file", "file"),
    ("static_ancillary_file_group", "algorithm_parameters_overrides_json", "file"),
    ("input_file_group", "ascending_disp_files", "file"),
    ("input_file_group", "descending_disp_files", "file"),
    ("input_file_group", "ascending_cal_files", "file"),
    ("input_file_group", "descending_cal_files", "file"),
    ("input_file_group", "unr_grid_latlon_file", "file"),
    ("input_file_group", "unr_timeseries_dir", "dir"),
    ("dynamic_ancillary_file_group", "los_file_ascending", "file"),
    ("dynamic_ancillary_file_group", "los_file_descending", "file"),
    ("static_ancillary_file_group", "gia_model_file", "file"),
)


class PrimaryExecutable(YamlModel):
    """Group describing the primary executable."""

    product_type: Literal["VLM"] = Field(
        default=PRODUCT_TYPE,
        description="Product type of the PGE.",
    )
    model_config = STRICT_CONFIG_WITH_ALIASES


class OutputOptions(YamlModel):
    """Product-level options set by the PGE (not science parameters)."""

    product_version: str = Field(
        default="0.1",
        pattern=r"^\d+\.\d+$",
        description="Version of the product, in <major>.<minor> format.",
    )
    compression: bool = Field(
        default=True,
        description="Write raster layers gzip-compressed (level 4 + shuffle).",
    )
    processing_facility: str = Field(
        default="NASA Jet Propulsion Laboratory on AWS",
        description="Processing facility written to /identification.",
    )
    product_data_access: str = Field(
        default="",
        description="URL (or DOI) where this product can be retrieved.",
    )
    model_config = STRICT_CONFIG_WITH_ALIASES


class ProductPathGroup(YamlModel):
    """Group describing the product paths."""

    product_path: DirectoryPath = Field(
        default=Path(),
        description="Directory where PGE will place results.",
    )
    scratch_path: DirectoryPath = Field(
        default=Path("./scratch"),
        description="Path to the scratch directory for intermediate files.",
    )
    output_path: DirectoryPath = Field(
        default=Path("./output"),
        description="Path to the SAS output directory.",
        alias="sas_output_path",
    )
    keep_scratch: bool = Field(
        default=False,
        description="Keep the scratch directory after a successful run (debugging).",
    )
    model_config = STRICT_CONFIG_WITH_ALIASES


class RunConfig(YamlModel):
    """A PGE (Product Generation Executive) run configuration."""

    _yaml_root_key: ClassVar[str] = "opera_vlm_workflow"

    input_file_group: InputFileGroup = Field(
        ..., description="Configuration for required input files."
    )
    dynamic_ancillary_file_group: DynamicAncillaryFileGroup = Field(
        ..., description="Ancillary files that change per job."
    )
    static_ancillary_file_group: StaticAncillaryFileGroup = Field(
        default_factory=StaticAncillaryFileGroup,
        description="Versioned, job-independent ancillary databases.",
    )
    primary_executable: PrimaryExecutable = Field(
        default_factory=PrimaryExecutable,
        description="Primary executable configuration.",
    )
    output_options: OutputOptions = Field(
        default_factory=OutputOptions, description="Output product options."
    )
    product_path_group: ProductPathGroup = Field(
        default_factory=ProductPathGroup, description="Product path configuration."
    )
    worker_settings: WorkerSettings = Field(
        default_factory=WorkerSettings,
        description="CPU/threading and block-size configuration.",
    )
    log_file: Optional[Path] = Field(
        default=None,
        description=(
            "Path to the output log file in addition to logging to stderr. If"
            " null, <sas_output_path>/opera_vlm.log."
        ),
    )
    run_input_prechecks: bool = Field(
        default=True,
        description=(
            "Run the numbered input prechecks (docs/error-codes.md) before"
            " processing. Escape hatch for operators; leave true."
        ),
    )

    model_config = STRICT_CONFIG_WITH_ALIASES

    # ------------------------------------------------------------------ IO
    @classmethod
    def from_yaml_file(cls, yaml_path: Path | str) -> "RunConfig":
        """Load and validate a runconfig, unwrapping the root key.

        Raises
        ------
        RunConfigError
            Unreadable YAML or a schema violation (exit code 3).

        """
        from ruamel.yaml import YAML, YAMLError

        try:
            with open(yaml_path) as f:
                data = YAML(typ="safe").load(f)
        except (OSError, YAMLError) as e:
            raise RunConfigError(f"Cannot read runconfig {yaml_path}: {e}") from e
        if isinstance(data, dict) and cls._yaml_root_key in data:
            data = data[cls._yaml_root_key]
        try:
            return cls.model_validate(data)
        except ValidationError as e:
            raise RunConfigError(f"Invalid runconfig {yaml_path}:\n{e}") from e

    # ----------------------------------------------------------- prechecks
    def precheck_inputs(self) -> None:
        """Fail fast, before any processing, on missing or wrong-kind inputs.

        Raises
        ------
        InputValidationError
            With a numbered code from `opera_vlm.errors.ERROR_CODES`.

        """
        problems_missing, problems_kind = [], []
        for group_name, field, kind in PATH_INPUTS:
            value = getattr(getattr(self, group_name), field)
            for path in value if isinstance(value, list) else [value]:
                if path is None:
                    continue
                if not path.exists():
                    problems_missing.append(f"{group_name}.{field}: {path}")
                elif (kind == "dir") != path.is_dir():
                    problems_kind.append(
                        f"{group_name}.{field}: {path} (expected {kind})"
                    )
        if problems_missing:
            raise InputValidationError(
                "Missing inputs: " + "; ".join(problems_missing), 1000
            )
        if problems_kind:
            raise InputValidationError(
                "Wrong input kind: " + "; ".join(problems_kind), 1001
            )

    # ------------------------------------------------------------ resolve
    def load_algorithm_parameters(self) -> tuple[AlgorithmParameters, dict]:
        """Algorithm parameters file + the overrides for this job.

        Returns the resolved parameters and the overrides that were applied
        (logged, and recorded in the product metadata).
        """
        dyn, sta = self.dynamic_ancillary_file_group, self.static_ancillary_file_group
        try:
            params = AlgorithmParameters.from_yaml(dyn.algorithm_parameters_file)
            overrides = read_overrides(
                sta.algorithm_parameters_overrides_json, self._override_key()
            )
            if overrides:
                logger.info(
                    "Algorithm parameter overrides for %s=%s from %s: %s",
                    "frame_id",
                    self._override_key(),
                    sta.algorithm_parameters_overrides_json,
                    overrides,
                )
            return params.with_overrides(overrides), overrides
        except (OSError, ValueError, ValidationError) as e:
            raise InputValidationError(f"Algorithm parameters: {e}", 1002) from e

    def _override_key(self) -> str:
        """Key into the overrides JSON (frame ID for frame-based SAS)."""
        group = self.input_file_group
        return str(getattr(group, "frame_id", "default"))

    def resolved_log_file(self) -> Path:
        """`log_file`, defaulting to <sas_output_path>/opera_vlm.log."""
        log_file = (
            self.log_file or self.product_path_group.output_path / "opera_vlm.log"
        )
        return Path(log_file).resolve()

    def to_workflow(self) -> Workflow:
        """Resolve this runconfig into the internal, fully-specified `Workflow`."""
        paths = self.product_path_group
        if paths.product_path.resolve() != paths.output_path.resolve():
            logger.info(
                "product_path (%s) differs from sas_output_path (%s); the SAS"
                " writes to sas_output_path, the PGE moves products to product_path",
                paths.product_path,
                paths.output_path,
            )
        if self.run_input_prechecks:
            self.precheck_inputs()
        else:
            logger.warning("run_input_prechecks is false: input prechecks skipped")
        params, overrides = self.load_algorithm_parameters()
        return Workflow(
            input_file_group=self.input_file_group,
            dynamic_ancillary_file_group=self.dynamic_ancillary_file_group,
            static_ancillary_file_group=self.static_ancillary_file_group,
            algorithm_parameters=params,
            applied_overrides=overrides,
            work_directory=paths.scratch_path.resolve(),
            output_directory=paths.output_path.resolve(),
            keep_scratch=paths.keep_scratch,
            output_options=self.output_options.model_dump(),
            worker_settings=self.worker_settings,
            log_file=self.resolved_log_file(),
        )
