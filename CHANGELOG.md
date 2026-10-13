# Changelog

Format: [Keep a Changelog](https://keepachangelog.com). Versions come from git
tags (setuptools_scm). Mark entries that change product values with **[product]**.

## [Unreleased]

### Added
- **[product]** The VLM workflow (plan T56.2): `opera-vlm run` reads the
  ascending (and optional descending) DISP + DISP-CAL stacks, chains each
  geometry, resamples both onto common target epochs every
  `temporal_options.target_spacing_days` (new, default 12) with
  `venti.temporal`, takes GNSS east/north from `venti.gnss.vlm` (provenance
  checked against DISP-CAL) and decomposes with `venti.decomposition`. One
  product per target pair `(T0, Tk)`; `run` now returns the list of products.
- **[product]** `decomposition_options.sigma_disp_meters` default 0.01 ->
  0.007 m (TS-S1 per-point DISP noise); per-frame values in
  `configs/static/opera-vlm-algorithm-parameters-overrides-2026-10-10.json`.
- **[product]** `input_options.mask_layers` (default `["water_mask"]`): DISP
  masks applied to every pair before chaining.
- `static_ancillary_file_group.defo_area_db_json` (optional): the deforming-area
  database DISP-CAL used, needed with `gnss_options.exclude_defo_nodes`.
- Synthetic asc/desc frame with known east/north/up (`tests/synthetic.py`) and
  a 128 x 128 regression test (plan T56.4).

- Context layers (plan T56.3), never removed from the product:
  `plate_motion_east_rate` / `plate_motion_north_rate` (rigid plate,
  ITRF2020-PMM via `geepers.euler`; plate from Venti's frame table or
  `context_options.plate`) and `gia_vertical_rate` (ICE-6G_D, when
  `gia_model_file` is given). New `context_options` group.

### Changed
- Venti pin a0fe190 -> d67c452 (venti-dev main: `venti.gnss.vlm`).

### Not yet
- `output_options.write_velocity_product` fails with an algorithm error
  (exit 5) until the velocity-domain product is implemented.
- The first real asc/desc frame (T56.1).
- Initial scaffold (sas-scaffold).
