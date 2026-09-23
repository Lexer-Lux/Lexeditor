"""Issue #43 cartridge-velocity data for LEXEDITOR.

The XML mapping is authoritative: every row comes from a CWeaponInfo
DamageModes/Item/AmmoInfo relationship.  Multipliers are stored separately
because RDR2 exposes only one Speed field per weapon, not per damage mode.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path


CSV_FIELDS = ("ammo", "multiplier")


def default_multiplier(ammo: str) -> float:
    name = ammo.upper()
    if "HIGH_VELOCITY" in name:
        return 1.15
    if "EXPRESS_EXPLOSIVE" in name or "EXPLOSIVE" in name or "INCENDIARY" in name:
        return 0.85
    if "EXPRESS" in name or "_PLUS_P" in name or name.endswith("_P"):
        return 1.05
    if "SLUG" in name:
        return 1.00
    if "BUCKSHOT" in name or "SHOTGUN" in name:
        return 0.85
    if "ARROW_SMALL_GAME" in name:
        return 0.65
    if "ARROW" in name:
        return 0.55
    return 1.00


def cartridge_mapping(root):
    """Return every real weapon/damage-mode -> ammunition relationship."""
    mappings = []
    ammo_records = {
        (item.findtext("Name") or "").strip()
        for item in root.iter("Item")
        if (item.get("type") or "").startswith("CAmmo")
    }
    for weapon in root.iter("Item"):
        if weapon.get("type") != "CWeaponInfo":
            continue
        weapon_name = (weapon.findtext("Name") or "").strip()
        fire_type = (weapon.findtext("FireType") or "").strip()
        if not weapon_name:
            continue
        for mode in weapon.findall("./DamageModes/Item"):
            ammo = (mode.findtext("AmmoInfo") or "").strip()
            damage_mode = (mode.findtext("Name") or "").strip()
            if not ammo:
                continue
            mappings.append({
                "ammo": ammo,
                "weapon": weapon_name,
                "damageMode": damage_mode,
                "fireType": fire_type,
                "ammoRecordPresent": ammo in ammo_records,
            })
    mappings.sort(key=lambda row: (row["ammo"], row["weapon"], row["damageMode"]))
    return mappings


def load_multipliers(path: Path, ammo_names):
    values = {name: default_multiplier(name) for name in ammo_names}
    if not path.exists():
        return values
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != CSV_FIELDS:
            raise ValueError("projectile speed CSV must have columns: ammo,multiplier")
        seen = set()
        for line, row in enumerate(reader, 2):
            ammo = (row.get("ammo") or "").strip()
            if ammo not in values:
                raise ValueError(f"line {line}: unknown ammunition {ammo!r}")
            if ammo in seen:
                raise ValueError(f"line {line}: duplicate ammunition {ammo}")
            seen.add(ammo)
            try:
                multiplier = float(row.get("multiplier") or "")
            except ValueError as exc:
                raise ValueError(f"line {line}: multiplier must be numeric") from exc
            if not 0.05 <= multiplier <= 10.0:
                raise ValueError(f"line {line}: multiplier must be 0.05..10")
            values[ammo] = multiplier
    return values


def serialize_multipliers(values, ammo_names):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    for ammo in sorted(ammo_names):
        writer.writerow({"ammo": ammo, "multiplier": f"{float(values[ammo]):.4f}"})
    return output.getvalue()
