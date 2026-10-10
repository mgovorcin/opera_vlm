# VLM-S1 product specification

File name: `OPERA_<level>_<short name>_F<frame>_<start>_<end>_v<version>_<processing>.nc` (level `L4`, short name `VLM-S1`)

One run writes one product per target pair `(T0, Tk)`: target epochs are
every `temporal_options.target_spacing_days` over the span both geometries
cover, and `T0` (the first) is the reference of every product of the run.
`/identification` also carries `gnss_provenance_digest` (the GNSS realisation
used for north and, in mode 2, east) and `number_of_looks` (1 or 2).

Keep this page in sync with `src/opera_vlm/product/_layers.py` (the layer table
in code). Groups:

| Group | Content |
|---|---|
| `/` | Product layers (see `LAYERS`), `x`, `y`, `spatial_ref` |
| `/identification` | Searchable scalars: product type/version, dates, frame, processing facility, source granules |
| CEOS-ARD | Fields declared in `product/_ceos.py`, written into `/identification` and `/metadata`; matrix: [ceos-compliance.md](ceos-compliance.md) |
| `/metadata` | Provenance: SAS + dependency versions, algorithm parameters (after overrides), applied overrides, PGE runconfig, resolved workflow |
