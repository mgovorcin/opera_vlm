# VLM-S1 product specification

File name: `OPERA_<level>_<short name>_F<frame>_<start>_<end>_v<version>_<processing>.nc` (level `L4`, short name `VLM-S1`)

One run writes one product per target pair `(T0, Tk)`: target epochs are
every `temporal_options.target_spacing_days` over the span both geometries
cover, and `T0` (the first) is the reference of every product of the run.
Context layers (meters per year, not removed from any layer):
`plate_motion_east_rate` and `plate_motion_north_rate` (the frame's rigid
plate in ITRF2020-PMM; `east - rate * span` is plate-fixed) and
`gia_vertical_rate` (only when a GIA model file is given). `/identification`
names the `plate`, `plate_motion_model` and `gia_model`.

`/identification` also carries `gnss_provenance_digest` (the GNSS realisation
used for north and, in mode 2, east) and `number_of_looks` (1 or 2).

Keep this page in sync with `src/opera_vlm/product/_layers.py` (the layer table
in code). Groups:

| Group | Content |
|---|---|
| `/` | Product layers (see `LAYERS`), `x`, `y` (pixel centres, CF `projection_x/y_coordinate`), `spatial_ref` (CF grid mapping: `crs_wkt`, GDAL `spatial_ref` + `GeoTransform`; every 2-D layer has `grid_mapping = "spatial_ref"`) |
| `/identification` | Searchable scalars: product type/version, dates, frame, processing facility, source granules |
| CEOS-ARD | Fields declared in `product/_ceos.py`, written into `/identification` and `/metadata`; matrix: [ceos-compliance.md](ceos-compliance.md) |
| `/metadata` | Provenance: SAS + dependency versions, algorithm parameters (after overrides), applied overrides, PGE runconfig, resolved workflow |
