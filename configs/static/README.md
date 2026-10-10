# Static ancillary files

Versioned, job-independent databases delivered with the SAS (frame DB,
per-frame algorithm overrides, event catalogues).

Rules:
- **Dated, never edited in place.** A change is a new file
  (`opera-opera-vlm-algorithm-parameters-overrides-YYYY-MM-DD.json`); the PGE
  points the runconfig at the new one. Old products stay reproducible.
- Each file carries a `"metadata"` block (creation date, author, reason) next
  to `"data"`.
- Large files (> 1 MB) are not committed: publish them (release asset / S3)
  and record the URL + sha256 here.

| File | Purpose | sha256 |
|---|---|---|
| `opera-vlm-algorithm-parameters-overrides-2026-10-10.json` | Per-frame `sigma_disp_meters` from TS-S1 (F08882, F08886, F16940, F08622) | in git |
