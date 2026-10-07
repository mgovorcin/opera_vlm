# CLAUDE.md — opera-vlm

<!-- Structure: 00_tools/standards/CLAUDE.md.template. Scaffolded by the
     sas-scaffold skill; keep it short, long explanations go in docs/. -->

## What this repo is

The OPERA Science Algorithm Software (SAS) for `VLM` (OPERA Vertical Land Motion from DISP and DISP-CAL).
It turns one PGE runconfig into one `VLM-S1` product. It does **not**
download inputs during `run` (that is `opera-vlm stage`), schedule jobs, or move
products (the PGE does).

## Architecture

```
src/opera_vlm/
  cli/            click: run, config, validate, ceos, stage   (entry point: opera-vlm run RUNCONFIG)
  config/         pydantic: PGE RunConfig -> resolved Workflow; algorithm params + overrides
  algorithm.py    run_algorithm(Workflow) -> AlgorithmResult   (the science)
  product/        LAYERS spec, writer, /identification + /metadata, CEOS-ARD registry, browse
  stage/          downloaders, never imported by run
  validate.py     golden comparison
  errors.py       exit codes + numbered input errors
```

## Invariants (do not break without a decision record)

- The runconfig and CLI are the PGE interface: fields are added, never renamed
  or removed; `extra="forbid"` stays.
- `configs/` and `docs/ceos-compliance.md` are generated (`pixi run gen-configs`);
  never hand-edited. CI diffs them.
- Science settings live in algorithm parameters, never in the runconfig;
  paths and threads never in algorithm parameters.
- Every algorithm parameter has a default; overrides are deep-merged and
  re-validated (unknown keys fail).
- Exit codes and `[error NNNN]` codes are never reused or renumbered;
  every code is in `docs/error-codes.md`.
- Every CEOS field goes through `product/_ceos.py`; `opera-vlm ceos check` must be
  COMPLIANT on the golden product before a delivery.
- `run` reads only files listed in the runconfig: no network, no hidden paths.

## Commands

```bash
pixi install -e dev
pixi run test          # pytest
pixi run lint          # pre-commit run -a
pixi run docs          # mkdocs build --strict
pixi run gen-configs   # regenerate configs/ + CEOS matrix
pixi run golden --golden-dir DIR   # golden regression
opera-vlm config template | algorithm | runconfig ... | schema
opera-vlm run runconfig.yaml
opera-vlm ceos check PRODUCT
```

<!-- Machine notes: TMPDIR=/u/aurora-r0/govorcin/tmp; RATTLER_CACHE_DIR and
     UV_CACHE_DIR on the big disk; NUMPY_MADVISE_HUGEPAGE=0 for full-frame runs. -->

## Golden / value-change policy

Any change that can alter what a run produces either leaves the regression
tests green or updates the golden **deliberately**, in the same PR, with the
difference explained in the PR body and CHANGELOG (**[product]** entry). See
the `workflow-regression` skill. Rebuild the golden inside the delivered image
(`scripts/build_golden_output.sh`).

## Conventions

- Branches: never commit on `main`; `feature/<topic>` for one concern; PRs to
  the fork's `main` are reviewed by the owner. See `CONTRIBUTING.md`.
- Every addition ships with its test in the same commit (`unit-tests` skill).
- Style: ruff + black + mypy via pre-commit; NumPyDoc docstrings; SPDX header
  (`Apache-2.0`) on every `.py` file.
