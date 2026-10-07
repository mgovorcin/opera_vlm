# opera-vlm

OPERA Vertical Land Motion from DISP and DISP-CAL — OPERA Science Algorithm Software (SAS) producing `VLM`
products.

## Install

```bash
pixi install            # runtime env (conda-forge + this package, editable)
pixi run -e dev test    # tests
pixi run -e dev lint    # pre-commit: ruff, black, mypy, SPDX headers, shellcheck
```

Without pixi: `mamba env create -f environment.yml`.

## Run

```bash
opera-vlm config algorithm -o algorithm_parameters.yaml   # defaults (edit or --set)
opera-vlm config runconfig ... -a algorithm_parameters.yaml -c runconfig.yaml
opera-vlm run runconfig.yaml
opera-vlm validate GOLDEN.nc TEST.nc
```

`opera-vlm config template` prints an empty, commented runconfig;
`opera-vlm config schema` prints its JSON Schema (for the PGE team).

## Interface

| File | Owner | Purpose |
|---|---|---|
| runconfig (`configs/runconfig.yaml`) | PGE | Job inputs, ancillaries, output paths, workers |
| algorithm parameters (`configs/algorithm_parameters.yaml`) | SAS team | Science knobs, defaults |
| overrides JSON (`configs/static/`) | SAS team | Per-frame_id values merged on top |

Inputs:

| Field | Group | Type | Required | Description |
|---|---|---|---|---|
| `frame_id` | input | int | yes | Frame ID of the products to process. |
| `algorithm_parameters_file` | dynamic | file | yes | Path to file containing SAS algorithm parameters (YAML). |
| `algorithm_parameters_overrides_json` | static | file | no | JSON file of per-frame_id algorithm parameter overrides applied on top of the algorithm_parameters_file. Format: {"data": {"<frame_id>": {<option group>: {<option>: <value>}}}}. |
| `ascending_disp_files` | input | files | yes | Ascending DISP products (DISP-S1 for VLM-S1, DISP-NISAR for VLM-NI) of the frame stack. |
| `descending_disp_files` | input | files | no | Descending DISP products over the same area. If absent, vertical comes from the single-geometry projection (mode 2) everywhere. |
| `ascending_cal_files` | input | files | yes | DISP-CAL products matching each ascending DISP product (same reference/secondary dates). |
| `descending_cal_files` | input | files | no | DISP-CAL products matching each descending DISP product; required when descending_disp_files is given. |
| `unr_grid_latlon_file` | input | file | no | UNR grid lookup of the frozen snapshot. Used for GNSS east/north only when the DISP-CAL products carry no gnss_ve/gnss_vn layers; the provenance hash must then match the one in DISP-CAL. |
| `unr_timeseries_dir` | input | dir | no | Node files of the frozen UNR snapshot (nodes/ of unr_grid_<version>_<date>); see unr_grid_latlon_file. |
| `los_file_ascending` | dynamic | file | yes | DISP-S1-STATIC line_of_sight_enu of the ascending frame. |
| `los_file_descending` | dynamic | file | no | DISP-S1-STATIC line_of_sight_enu of the descending frame; required with descending inputs. |
| `gia_model_file` | static | file | no | GIA vertical-rate model (ICE-6G_D) for the context layer; omitted -> no GIA context layer. |

Exit codes and numbered input errors: [docs/error-codes.md](docs/error-codes.md).

## CEOS-ARD compliance

CEOS Analysis Ready Data fields are declared once in
`src/opera_vlm/product/_ceos.py` (PFS section, group, and whether the value is
static, computed from the product, or supplied by the algorithm). The matrix
[docs/ceos-compliance.md](docs/ceos-compliance.md) is generated from it.

```bash
opera-vlm ceos check OPERA_....nc   # ok / missing / placeholder per field; exit 1 if not compliant
opera-vlm ceos matrix                     # the compliance matrix
```

## Staging inputs

`opera-vlm stage --help` downloads inputs for local runs (needs `pip install
"opera-vlm[stage]"`). `run` never downloads.

## Docker

```bash
docker/build-docker-image.sh -t mgovorcin/opera-vlm:dev
docker run --rm --user $(id -u):$(id -g) -v $PWD:/home/work mgovorcin/opera-vlm:dev opera-vlm run runconfig.yaml
```

## Golden dataset

```bash
scripts/build_golden_output.sh --output-dir golden_data   # deliberate act; inside the image
pixi run golden --golden-dir golden_data
```
