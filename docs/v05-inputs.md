# Running on cal-disp v0.5 inputs

cal-disp v0.5.0 and later calibrate with **remove-restore**: GNSS grid nodes
inside deforming areas are excluded and re-interpolated, from Venti's area
database. Each DISP-CAL product records how its GNSS field was made in
`/metadata/gnss_provenance`. `opera-vlm run` samples GNSS itself and checks
that its realisation matches the one in every DISP-CAL product. If it does not,
the run stops with:

```text
[error 1003] GNSS realisation differs from DISP-CAL (...): defo_db_version: DISP-CAL '1.1-draft' vs VLM None; ...
```

To match a v0.5 DISP-CAL stack, give the VLM run the same GNSS settings:

```yaml
# algorithm parameters
gnss_options:
  buffer_meters: 50000.0
  exclude_defo_nodes: true
  reinterpolate_excluded: true
```

```yaml
# runconfig
static_ancillary_file_group:
  defo_area_db_json: <the area database cal-disp used>   # e.g. Venti's data/defo_area_db_v1.geojson
```

- **The area database must be the same file** (its top-level `version` is in
  the provenance, e.g. `1.1-draft`). It is the one in the DISP-CAL runconfig's
  `static_ancillary_group.defo_area_db_json`.
- **opera_vlm reads the version the way cal-disp does** (Venti's
  `load_area_db`), since opera_vlm #17. Earlier versions could not match any
  remove-restore DISP-CAL product.
- **The GNSS inputs must be the same UNR grid** (`unr_grid_latlon_file`,
  `unr_timeseries_dir`) and grid type as DISP-CAL's.

Example: Houston, F08882 (ascending) + F38238 (descending), on the cal-disp
v0.5.0 confirmation-run products: 14 products, 2 h 57 min, 12.4 GB peak.
