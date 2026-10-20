# Changelog

Format: [Keep a Changelog](https://keepachangelog.com). Versions come from git
tags (setuptools_scm). Mark entries that change product values with **[product]**.

## [Unreleased]

### Fixed
- **[product]** Products are georeferenced (CF-1.8 + GDAL), as
  `docs/product-spec.md` already promised: a scalar `spatial_ref` grid mapping
  (CF grid-mapping attributes, `crs_wkt`, `spatial_ref` WKT, `GeoTransform`),
  `grid_mapping = "spatial_ref"` on every 2-D layer and CF
  `standard_name`/`units` on `x`/`y`. Before, the CRS was only the global
  `epsg` attribute (kept), so GDAL and CF readers could not place the layers.
  Layer values are unchanged; the structure gains one variable and attributes
  (additive, ADR 0002). No golden product had been delivered yet.
- CEOS-ARD: new computed field `identification/product_coordinate_reference_system`
  (PFS 1.7.9, `EPSG:<code> (<name>)`); `opera-vlm ceos check` reports it
  `ungridded` (NOT COMPLIANT) unless every 2-D layer points at the
  `spatial_ref` grid mapping.

## [0.1.0] — unreleased (Venti plan T57.3; tag `v0.1.0` by the owner)

First release: VLM per target pair from DISP-S1 + DISP-CAL, validated on LA
(passes the VLM gate) and Houston (edge case). Frozen interfaces: ADR 0002.

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
- **[product]** `decomposition_options.sigma_rate_meters_per_year` (default
  0.0015): per-look sigma grows as (rate x span) in quadrature. Fitted on LA
  (F16940 + F18904) GNSS residuals: robust z spread flat at ~0.9 across 0.5-7
  yr spans (was 0.87 -> 1.52), coverage 78% -> 85% (T57).
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

### Fixed
- The area-database version is read with Venti's `load_area_db`, as cal-disp
  does: VLM runs now match remove-restore DISP-CAL (cal-disp v0.5.0) instead
  of failing with error 1003 (#17).

### Docs
- ADR 0002 (v0.1 frozen interfaces); *Running on cal-disp v0.5 inputs*.

### Not yet
- `output_options.write_velocity_product` fails with an algorithm error
  (exit 5) until the velocity-domain product is implemented.
- Initial scaffold (sas-scaffold).
