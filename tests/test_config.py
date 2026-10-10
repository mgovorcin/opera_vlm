# SPDX-FileCopyrightText: 2026 California Institute of Technology ("Caltech")
# SPDX-License-Identifier: Apache-2.0
# Part of opera-vlm, https://github.com/mgovorcin/opera-vlm.
from __future__ import annotations

import json
from pathlib import Path

import pytest

from opera_vlm.config import AlgorithmParameters, RunConfig
from opera_vlm.config._utils import parse_set_option, read_overrides
from opera_vlm.errors import InputValidationError, RunConfigError


def test_runconfig_roundtrip(runconfig_file: Path, tmp_path: Path):
    rc = RunConfig.from_yaml_file(runconfig_file)
    out = tmp_path / "again.yaml"
    rc.to_yaml(out)
    assert RunConfig.from_yaml_file(out) == rc


def test_unknown_key_rejected(runconfig_file: Path):
    text = runconfig_file.read_text().replace(
        "worker_settings:", "worker_settings:\n    not_a_field: 1", 1
    )
    runconfig_file.write_text(text)
    with pytest.raises(RunConfigError, match="not_a_field"):
        RunConfig.from_yaml_file(runconfig_file)


def test_missing_input_has_error_code(runconfig_file: Path):
    rc = RunConfig.from_yaml_file(runconfig_file)
    rc.dynamic_ancillary_file_group.algorithm_parameters_file = Path(
        "/does/not/exist.yaml"
    )
    with pytest.raises(InputValidationError, match=r"\[error 1000\]"):
        rc.precheck_inputs()


def test_to_workflow_resolves_paths(runconfig_file: Path):
    wf = RunConfig.from_yaml_file(runconfig_file).to_workflow()
    assert wf.work_directory.is_absolute()
    assert wf.output_directory.is_absolute()
    assert wf.log_file is not None and wf.log_file.is_absolute()


def test_overrides_applied_for_key(runconfig_file: Path, tmp_path: Path):
    rc = RunConfig.from_yaml_file(runconfig_file)
    key = rc._override_key()
    group, option, value = _first_option()
    overrides = tmp_path / "overrides.json"
    overrides.write_text(json.dumps({"data": {key: {group: {option: value}}}}))
    rc.static_ancillary_file_group.algorithm_parameters_overrides_json = overrides
    wf = rc.to_workflow()
    assert getattr(getattr(wf.algorithm_parameters, group), option) == value
    assert wf.applied_overrides == {group: {option: value}}


def test_unknown_override_fails_loudly():
    with pytest.raises(ValueError):
        AlgorithmParameters().with_overrides({"definitely_not_an_option": 1})


def test_read_overrides_formats(tmp_path: Path):
    f = tmp_path / "o.json"
    f.write_text(json.dumps({"7": {"a": 1}}))
    assert read_overrides(f, 7) == {"a": 1}
    f.write_text(json.dumps({"data": {"7": {"a": 1}}}))
    assert read_overrides(f, "7") == {"a": 1}
    assert read_overrides(f, 8) == {}
    assert read_overrides(None, 7) == {}


def test_parse_set_option():
    assert parse_set_option(["a.b=3", "a.c=true", "d=text"]) == {
        "a": {"b": 3, "c": True},
        "d": "text",
    }


def _first_option() -> tuple[str, str, object]:
    """A (group, option, new value) triple that validates and differs from the default."""
    params = AlgorithmParameters()
    for group in type(params).model_fields:
        options = getattr(params, group)
        for option in type(options).model_fields:
            default = getattr(options, option)
            if isinstance(default, bool):
                candidates: list = [not default]
            elif isinstance(default, (int, float)):
                candidates = [default + 1, default * 2, default - 1]
            else:
                continue
            for value in candidates:
                try:
                    params.with_overrides({group: {option: value}})
                except ValueError:
                    continue
                return group, option, value
    pytest.skip("no numeric/bool option to override")


def test_vlm_product_and_gnss_options_draft():
    """T52.2 draft: per-pair product official, velocity product opt-in; GNSS
    options mirror DISP-CAL so the provenance check can pass."""
    from pydantic import ValidationError

    from opera_vlm.config._algorithm import GnssOptions
    from opera_vlm.config.pge_runconfig import OutputOptions

    assert OutputOptions().write_velocity_product is False
    assert OutputOptions(write_velocity_product=True).write_velocity_product
    g = GnssOptions()
    assert g.require_provenance_match is True
    assert g.buffer_meters == 50_000.0
    assert not g.exclude_defo_nodes and not g.reinterpolate_excluded
    with pytest.raises(ValidationError):
        GnssOptions(buffer_meters=-1)
    with pytest.raises(ValidationError):
        GnssOptions(unknown_option=1)
