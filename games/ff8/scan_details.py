"""Generate accurate, data-driven extra Scan information for FF8 enemies.

The enemy DAT stores elemental defence percentages and one Devour result for
its low/medium/high data tiers.  This module deliberately uses the tier names
instead of pretending their numeric level cut-offs are universal: a small set
of vanilla enemies use different cut-offs.
"""

from __future__ import annotations

ELEMENT_NAMES = ("Fire", "Ice", "Thunder", "Earth", "Poison", "Wind", "Water", "Holy")


def _percent(value: int) -> str:
    return f"{value}%"


def _element_groups(tables: dict) -> list[str]:
    groups: dict[str, list[str]] = {"Weak": [], "Resist": [], "Immune": [], "Absorb": []}
    for entry in tables.get("elementDefence", []):
        slot = int(entry.get("slot", -1))
        if not 0 <= slot < len(ELEMENT_NAMES):
            continue
        value = int(entry.get("percent", 100))
        name = ELEMENT_NAMES[slot]
        if value > 100:
            groups["Weak"].append(f"{name} {_percent(value)}")
        elif 0 < value < 100:
            groups["Resist"].append(f"{name} {_percent(value)}")
        elif value == 0:
            groups["Immune"].append(name)
        elif value < 0:
            groups["Absorb"].append(f"{name} {_percent(abs(value))}")
    return [f"{label}: {', '.join(values)}" for label, values in groups.items() if values]


def _devour_name(value: int, choices: list[dict]) -> str:
    match = next((row for row in choices if int(row["id"]) == int(value)), None)
    return str(match["name"]) if match else f"Unknown {int(value)}"


def build_page(tables: dict, devour_choices: list[dict]) -> str:
    """Return an FF8-encodable extra Scan page, without the NewPage token."""
    lines = ["DETAILS"]
    element_lines = _element_groups(tables)
    lines.extend(element_lines or ["Elements: Neutral"])
    tiers = ("Low", "Mid", "High")
    devour = tables.get("devour", [])
    by_slot = {int(entry.get("slot", -1)): int(entry.get("devourId", 255)) for entry in devour}
    for slot, tier in enumerate(tiers):
        lines.append(f"Devour {tier}: {_devour_name(by_slot.get(slot, 255), devour_choices)}")
    return "\n".join(lines)
