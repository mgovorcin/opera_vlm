#!/usr/bin/env bash
# Build the golden dataset in the delivery layout (see run_validation.sh).
#
# usage: scripts/build_golden_output.sh [--output-dir DIR] [--skip-stage]
#
# Run it inside the delivered Docker image: the golden product is only
# reproducible to tolerance in the same software environment.
#   docker run --rm --user $(id -u):$(id -g) -v $PWD:/home/work -w /home/work \
#       -v ~/.netrc:/home/conda/.netrc:ro <image> bash opera-vlm/scripts/build_golden_output.sh
#
# Rebuilding the golden is a deliberate act: commit the reason (what changed
# in the product and why) with the new version of the dataset.
set -euo pipefail

OUTPUT_DIR="golden_data"
SKIP_STAGE=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
        --skip-stage) SKIP_STAGE=true; shift ;;
        -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

# TODO(sas): the golden case (one small, representative job)
# FRAME_ID=...
# START=...; END=...

mkdir -p "$OUTPUT_DIR"/{configs,input_data,golden_output,output}
OUTPUT_DIR="$(realpath "$OUTPUT_DIR")"

if [[ "$SKIP_STAGE" == false ]]; then
    echo "[1/3] Staging inputs into $OUTPUT_DIR/input_data"
    # TODO(sas): one `opera-vlm stage <source>` call per input, e.g.
    # opera-vlm stage <source> --frame-id "$FRAME_ID" -o "$OUTPUT_DIR/input_data/<source>"
    echo "TODO: staging not implemented in build_golden_output.sh" >&2
    exit 1
fi

echo "[2/3] Writing configs"
opera-vlm config algorithm -o "$OUTPUT_DIR/configs/algorithm_parameters.yaml"
# TODO(sas): `opera-vlm config runconfig ... -c "$OUTPUT_DIR/configs/runconfig.yaml"`,
# then rewrite the absolute paths relative to $OUTPUT_DIR so the dataset is relocatable:
#   sed -i "s#$OUTPUT_DIR/##g" "$OUTPUT_DIR/configs/runconfig.yaml"

echo "[3/3] Running and promoting the product to golden_output/"
(cd "$OUTPUT_DIR" && opera-vlm run configs/runconfig.yaml)
mv "$OUTPUT_DIR"/output/OPERA_* "$OUTPUT_DIR/golden_output/"
echo "Golden dataset ready: $OUTPUT_DIR (verify with scripts/run_validation.sh --golden-dir $OUTPUT_DIR)"
