# Exit codes and error codes

## Process exit codes (`opera-vlm run`)

| Exit | Meaning |
|---|---|
| 0 | Success |
| 1 | Unexpected error (bug): traceback in the log |
| 2 | Bad command-line usage |
| 3 | Runconfig unreadable or invalid (schema) |
| 4 | Input validation failed: see `[error NNNN]` below |
| 5 | Algorithm failed |
| 6 | Writing the product failed |

## Input validation codes

Logged as `[error NNNN] message`. Codes are never reused or renumbered.
Prechecks can be disabled with `run_input_prechecks: false` (operators only).

| Code | Meaning | Operator action |
|---|---|---|
| 1000 | Required input file or directory does not exist. | Check staging / runconfig paths. |
| 1001 | Input path has the wrong kind (file vs directory). | Fix the runconfig. |
| 1002 | Algorithm parameters file or overrides are invalid. | Check the delivered parameter / overrides files. |
| 1003 | Inputs are inconsistent with each other. | Check the job's input selection. |
