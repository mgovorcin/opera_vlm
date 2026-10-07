# SPDX-FileCopyrightText: 2026 California Institute of Technology ("Caltech")
# SPDX-License-Identifier: Apache-2.0
# Part of opera-vlm, https://github.com/mgovorcin/opera-vlm.
"""Path types and helpers shared by the configuration models."""

from __future__ import annotations

import glob
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Any, List

from pydantic import BeforeValidator


def _to_path_required(v: str | Path | None) -> Path:
    """Convert to Path, rejecting None/empty."""
    if v is None:
        raise ValueError("Path cannot be None")
    if isinstance(v, str):
        if not v.strip():
            raise ValueError("Path cannot be an empty string")
        return Path(v)
    return v


def _to_path_optional(v: str | Path | None) -> Path | None:
    """Convert to Path; None and empty strings become None."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    return Path(v)


def _to_path_or_cwd(v: str | Path | None) -> Path:
    """Convert to Path; None and empty strings become the current directory."""
    if v is None or v == "":
        return Path()
    return Path(v)


def _to_file_list(value: Any) -> list[Path]:
    """Accept a list, a glob pattern, or a text file listing one path per line.

    ``None``, ``""`` and ``[None]`` (what an empty YAML list item loads as)
    give an empty list.
    """
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple)):
        items = [v for v in value if v not in (None, "")]
        if len(items) == 1 and glob.has_magic(str(items[0])):
            return sorted(Path(f) for f in glob.glob(str(items[0])))
        return [Path(v) for v in items]
    if glob.has_magic(str(value)):
        return sorted(Path(f) for f in glob.glob(str(value)))
    path = Path(value)
    if path.suffix in {".txt", ".lst"} and path.is_file():
        lines = [ln.strip() for ln in path.read_text().splitlines() if ln.strip()]
        return [p if p.is_absolute() else path.parent / p for p in map(Path, lines)]
    return [path]


RequiredPath = Annotated[Path, BeforeValidator(_to_path_required)]
OptionalPath = Annotated[Path | None, BeforeValidator(_to_path_optional)]
DirectoryPath = Annotated[Path, BeforeValidator(_to_path_or_cwd)]
FileList = Annotated[List[Path], BeforeValidator(_to_file_list)]


def nested_update(base: dict[str, Any], new: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively merge `new` into `base` (in place) and return `base`."""
    for key, value in new.items():
        if isinstance(value, Mapping) and isinstance(base.get(key), dict):
            nested_update(base[key], value)
        else:
            base[key] = value
    return base


def read_overrides(overrides_file: Path | str | None, key: int | str) -> dict:
    """Return the overrides for `key` from an overrides JSON file.

    Accepts ``{"data": {"<key>": {...}}}`` (the delivered format, which leaves
    room for a ``"metadata"`` block) and plain ``{"<key>": {...}}``.
    """
    if overrides_file is None:
        return {}
    with open(overrides_file) as f:
        overrides = json.load(f)
    table = overrides.get("data", overrides)
    return table.get(str(key), {})


def parse_set_option(items: tuple[str, ...] | list[str]) -> dict[str, Any]:
    """Turn ``["group.option=VALUE", ...]`` into a nested dict.

    VALUE is parsed as JSON when possible (``3``, ``true``, ``null``,
    ``[1, 2]``), else kept as a string.
    """
    out: dict[str, Any] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"--set expects KEY=VALUE, got {item!r}")
        key, raw = item.split("=", 1)
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            value = raw
        node = out
        *parents, leaf = key.strip().split(".")
        for part in parents:
            node = node.setdefault(part, {})
        node[leaf] = value
    return out
