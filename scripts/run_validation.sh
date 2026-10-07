#!/usr/bin/env bash
# Validate this installation against a golden dataset.
#
# usage: scripts/run_validation.sh --golden-dir DIR [--rtol R] [--atol A]
#
# DIR layout (written by scripts/build_golden_output.sh):
#   configs/runconfig.yaml      paths relative to DIR
#   configs/algorithm_parameters.yaml
#   input_data/                 every input the runconfig lists
#   golden_output/              exactly one golden product (+ .png)
#   output/                     test products land here
#
# Exit codes: 0 passed, 1 failed (run error or product mismatch).
set -euo pipefail

GOLDEN_DIR=""
RTOL="1e-5"
ATOL="1e-6"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --golden-dir) GOLDEN_DIR="$2"; shift 2 ;;
        --rtol) RTOL="$2"; shift 2 ;;
        --atol) ATOL="$2"; shift 2 ;;
        -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done
[[ -n "$GOLDEN_DIR" ]] || { echo "ERROR: --golden-dir is required" >&2; exit 1; }
GOLDEN_DIR="$(realpath "$GOLDEN_DIR")"

mapfile -t GOLDEN < <(find "$GOLDEN_DIR/golden_output" -maxdepth 1 -name 'OPERA_*.nc' -type f)
if [[ "${#GOLDEN[@]}" -ne 1 ]]; then
    echo "ERROR: expected exactly one golden product in $GOLDEN_DIR/golden_output" >&2
    exit 1
fi

rm -f "$GOLDEN_DIR"/output/OPERA_*
mkdir -p "$GOLDEN_DIR/output"

echo "[1/2] Running opera-vlm on the golden inputs"
(cd "$GOLDEN_DIR" && opera-vlm run configs/runconfig.yaml)

mapfile -t TEST < <(find "$GOLDEN_DIR/output" -maxdepth 1 -name 'OPERA_*.nc' -type f)
[[ "${#TEST[@]}" -eq 1 ]] || { echo "ERROR: run produced ${#TEST[@]} products" >&2; exit 1; }

echo "[2/2] Comparing $(basename "${TEST[0]}") with $(basename "${GOLDEN[0]}")"
opera-vlm validate --rtol "$RTOL" --atol "$ATOL" "${GOLDEN[0]}" "${TEST[0]}"
