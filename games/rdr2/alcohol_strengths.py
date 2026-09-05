"""Load vanilla alcohol strengths and persist sparse GameplayTweaks overrides."""

from __future__ import annotations

import csv
import math
from collections.abc import Mapping
from pathlib import Path

try:
    from .paths import PROJECT_ROOT
except ImportError:
    from paths import PROJECT_ROOT


VANILLA_FILE = PROJECT_ROOT / "datasets" / "vanilla" / "alcohol_strengths.csv"
OVERRIDE_FILE = PROJECT_ROOT / "GameplayTweaks" / "alcohol_strengths.csv"


def _read_rows(path: Path) -> dict[str, float]:
    entries: dict[str, float] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for line_number, row in enumerate(csv.reader(handle), 1):
            if not row or not row[0].strip() or row[0].lstrip().startswith("#"):
                continue
            key = row[0].strip()
            if key in entries:
                raise ValueError(f"duplicate alcohol item {key} in {path}:{line_number}")
            try:
                value = float(row[1])
            except (IndexError, ValueError) as exc:
                raise ValueError(f"invalid alcohol strength in {path}:{line_number}") from exc
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(
                    f"alcohol strength must be on the 0-1 scale in {path}:{line_number}"
                )
            entries[key] = value
    return entries


def get_alcohol_strengths(
    vanilla_file: Path = VANILLA_FILE,
    override_file: Path = OVERRIDE_FILE,
) -> dict[str, object]:
    vanilla = _read_rows(vanilla_file)
    overrides = _read_rows(override_file) if override_file.exists() else {}
    unknown = sorted(set(overrides) - set(vanilla))
    if unknown:
        raise ValueError(f"alcohol override has no vanilla item: {', '.join(unknown)}")
    entries = dict(vanilla)
    entries.update(overrides)
    return {
        "available": vanilla_file.exists() and override_file.parent.exists(),
        "file": str(override_file),
        "source": str(vanilla_file),
        "entries": entries,
        "vanilla": vanilla,
        "overrides": overrides,
    }


def save_alcohol_strengths(
    entries: Mapping[str, object],
    vanilla_file: Path = VANILLA_FILE,
    override_file: Path = OVERRIDE_FILE,
) -> int:
    if not override_file.parent.exists():
        raise ValueError("the optional GameplayTweaks runtime extension is not installed")
    vanilla = _read_rows(vanilla_file)
    effective = dict(vanilla)
    if override_file.exists():
        current = _read_rows(override_file)
        effective.update({key: value for key, value in current.items() if key in vanilla})

    for raw_key, raw_value in entries.items():
        key = str(raw_key).strip()
        if key not in vanilla:
            raise ValueError(f"unknown alcohol item: {key}")
        try:
            value = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid alcohol strength for {key}") from exc
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError(f"alcohol strength for {key} must be on the 0-1 scale")
        effective[key] = value

    overrides = {
        key: effective[key]
        for key, baseline in vanilla.items()
        if not math.isclose(effective[key], baseline, rel_tol=0.0, abs_tol=1e-9)
    }
    lines = [
        "# Desired per-drink strength overrides. Columns 3-4 retain Rockstar's baseline and swig count.",
        "# item,target_strength_per_drink,vanilla_strength_per_drink,swigs",
    ]
    lines.extend(
        f"{key},{overrides[key]:g},{vanilla[key]:g},{_swigs_for(key, vanilla_file)}"
        for key in vanilla
        if key in overrides
    )
    temporary = override_file.with_suffix(override_file.suffix + ".tmp")
    temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    temporary.replace(override_file)
    return len(overrides)


def _swigs_for(key: str, vanilla_file: Path) -> int:
    with vanilla_file.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.reader(handle):
            if not row or row[0].strip() != key:
                continue
            try:
                return int(row[3])
            except (IndexError, ValueError):
                return 1
    return 1
