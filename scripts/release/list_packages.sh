#!/usr/bin/env bash
# Write the installed-packages CSV that goes with a delivery
# (name,version,build,channel), from inside the delivered image:
#   docker run --rm <image> bash -lc 'micromamba list --json' | scripts/release/list_packages.sh > Installed_Packages.csv
set -euo pipefail
python3 -c '
import csv, json, sys
rows = json.load(sys.stdin)
w = csv.writer(sys.stdout)
w.writerow(["name", "version", "build", "channel"])
for r in sorted(rows, key=lambda r: r["name"]):
    w.writerow([r["name"], r["version"], r.get("build_string", ""), r.get("channel", "")])
'
