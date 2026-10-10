# 0001. VLM runconfig and product: what is draft, what will be frozen

- **Status:** draft for review (plan T52.2 / T52.3, 2026-10-09)
- **Context:** Venti PRD §3.2 and D15. DISP-CAL's runconfig is frozen;
  VLM's is not yet, and this record says which parts will be.

## Decisions

1. **Products** (owner, 2026-10-09).
   - **VLM per pair is the official product.** Each ascending/descending
     pair date gives vertical (and east where both looks overlap)
     displacement, with σ and a mode layer.
   - **The velocity-domain product is optional**
     (`output_options.write_velocity_product`, default off). It calibrates
     the chained velocity once instead of chaining per-pair DISP-CAL.
   - Chaining per-pair calibrations spreads station residuals: on F08882,
     NMAD 1.5 → 2.9 mm/yr, against 2.2 for velocity-domain
     (disp2vlm_validation issue #3).
2. **North always comes from GNSS** (invariant).
   - It comes from the DISP-CAL `gnss_ve`/`gnss_vn` layers (T61) or from the
     grid snapshot through `venti.gnss.vlm.load_gnss_for_vlm`.
   - The realisation must match DISP-CAL's. `require_provenance_match`
     fails otherwise. `gnss_options.buffer_meters` (50 km),
     `exclude_defo_nodes` and `reinterpolate_excluded` mirror DISP-CAL's
     options so the check can pass.
3. **The mode is per pixel:** 0 none, 1 decomposed (WLS, both looks),
   2 projected (one look, or both looks ill-conditioned). These are
   `venti.decomposition`'s `MODE_WLS` and `MODE_PROJECTION`; an earlier draft
   of this record had 1 and 2 swapped.
4. **One run, one product per target pair** (T56.2, 2026-10-10, for owner
   review). A run takes the whole asc/desc stacks and writes a product for
   every target pair `(T0, Tk)`: `T0` is the first target epoch, targets are
   every `temporal_options.target_spacing_days` over the span both geometries
   cover. Like DISP-S1, every product of a run shares its reference date.

## To be frozen at VLM v0.1 (T57)

- The runconfig group and field names: `input_file_group`
  (`ascending_*` / `descending_*` DISP and CAL lists, UNR inputs),
  `dynamic_ancillary_file_group` (`algorithm_parameters_file`, LOS files),
  `static_ancillary_file_group`, `output_options`.
- The product layers: `vertical`, `vertical_std`, `east`, `east_std`,
  `mode`, plus the `/identification` and `/metadata` groups, including the
  GNSS provenance record.

## Still draft

- The algorithm parameters: decomposition `cond_max`, `min_up`,
  `sigma_disp_meters`; the temporal window and method. TS results may move
  them.
- The velocity-domain product's layers and their name.
- Context layers (`gia_rate`, `plate_motion_rate`).
