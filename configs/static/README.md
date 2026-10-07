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
