#!/usr/bin/env bash
# Regenerate the committed configs/ (and docs/ceos-compliance.md) from the code.
# CI runs this and fails on `git diff configs/` (tests/test_configs.py too).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
mkdir -p configs/schema
opera-vlm config template -o configs/runconfig.yaml
opera-vlm config algorithm -o configs/algorithm_parameters.yaml
opera-vlm config schema -o configs/schema/runconfig.schema.json
opera-vlm config schema --algorithm -o configs/schema/algorithm_parameters.schema.json
opera-vlm ceos matrix -o docs/ceos-compliance.md
