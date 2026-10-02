"""Validated, variable-length equipment-load bands and lossless schema migration.

Band identity/name belong to the project. Runtime projections deliberately omit
them: renaming a band must not needlessly change the executable.
"""
from __future__ import annotations

from copy import deepcopy
import math

MAX_BANDS = 32
MAX_NAME = 48
MAX_BOUND = 1000
MOVEMENTS = {1: "Light", 2: "Medium", 3: "Heavy", 4: "Overburdened"}
DEFAULT_BANDS = [
    {"id": 1, "name": "Light", "upper": 25.0, "movement": 1, "recovery": 100.0},
    {"id": 2, "name": "Medium", "upper": 50.0, "movement": 2, "recovery": 100.0},
    {"id": 3, "name": "Heavy", "upper": 100.0, "movement": 3, "recovery": 80.0},
    {"id": 4, "name": "Overburdened", "upper": None, "movement": 4, "recovery": 70.0},
]
DEFAULT_SPECIAL = {"enabled": True, "recovery": 100.0}
NATIVE_KEYS = {"baseRecovery", "bands", "specialLight", "forcedRecovery"}
PROJECT_KEYS = {"bands", "specialLight", "forcedRecovery"}

HELP = (
    "Split a band to add a range, or merge it with a neighbour to delete it. "
    "Each band selects a movement profile and its own stamina recovery. "
    "Adjacent bands with the same profile share a continuous movement range. "
    "Use 1 to 32 bands. The final band has no upper limit. "
    "Enable Encumbrance rules, save, then Apply."
)
UPPER_HELP = (
    "Includes this equipment load percentage. Lower limits follow the preceding band. "
    "The final band covers every higher load."
)
MOVEMENT_HELP = (
    "Uses the game's existing movement profile, not new animations. "
    "Adjacent bands with this profile share movement interpolation. "
    "An unbounded movement range uses the profile's starting interpolation value."
)
RECOVERY_HELP = (
    "Multiplies base recovery plus active effect bonuses. 100% keeps the full amount. "
    "This value is independent of the movement profile."
)
SPECIAL_HELP = (
    "The native special movement effect can replace Light with special-light movement. "
    "This is an effect-driven override, not another equipment-load range."
)
FORCED_HELP = (
    "Recovery while the native forced-overburdened condition is active. "
    "That condition takes priority over all load bands and the special-light override."
)


def percent(value, *, positive=False) -> float:
    lower = .01 if positive else 0
    if type(value) not in (int, float) or not lower <= value <= MAX_BOUND:
        raise ValueError(f"Enter a finite percentage from {lower} to {MAX_BOUND}")
    if not math.isfinite(value) or abs(round(value, 2) - value) > 1e-8:
        raise ValueError("Use at most two decimal places for percentages")
    return float(round(value, 2))


def validate_bands(value, *, project=True) -> list[dict]:
    if type(value) is not list or not 1 <= len(value) <= MAX_BANDS:
        raise ValueError(f"Use between 1 and {MAX_BANDS} load bands")
    fields = {"upper", "movement", "recovery"} | ({"id", "name"} if project else set())
    result, identities, lower = [], set(), 0.0
    for index, entry in enumerate(value):
        if type(entry) is not dict or set(entry) != fields:
            raise ValueError("Unsupported load-band fields")
        upper = entry["upper"]
        if index == len(value) - 1:
            if upper is not None:
                raise ValueError("The final band must have no upper limit")
        else:
            upper = percent(upper, positive=True)
            if upper <= lower:
                raise ValueError("Load-band upper limits must strictly increase")
        profile = entry["movement"]
        if type(profile) is not int or profile not in MOVEMENTS:
            raise ValueError("Choose an existing movement profile")
        row = {"upper": upper, "movement": profile, "recovery": percent(entry["recovery"])}
        if project:
            identity, name = entry["id"], entry["name"]
            if type(identity) is not int or not 1 <= identity <= 2**31 - 1024 or identity in identities:
                raise ValueError("Load-band identities must be distinct positive integers")
            if (type(name) is not str or not name.strip() or len(name) > MAX_NAME
                    or any(ord(char) < 32 or ord(char) == 127 for char in name)):
                raise ValueError(f"Give the band a name of 1 to {MAX_NAME} printable characters")
            identities.add(identity)
            row.update(id=identity, name=name)
        result.append(row)
        lower = upper
    return result


def special(value) -> dict:
    if (type(value) is not dict or set(value) != {"enabled", "recovery"}
            or type(value["enabled"]) is not bool):
        raise ValueError("Unsupported special-light override")
    return {"enabled": value["enabled"], "recovery": percent(value["recovery"])}


def validate_native(value) -> dict:
    if type(value) is not dict or set(value) != NATIVE_KEYS:
        raise ValueError("Unsupported variable-band native rules")
    base = value["baseRecovery"]
    if type(base) not in (int, float) or not 0 <= base <= 200 or not math.isfinite(base):
        raise ValueError("Base recovery must be a finite number from 0 to 200")
    # The existing native field is f32. Canonicalization prevents false stale comparisons.
    import struct
    base = struct.unpack("<f", struct.pack("<f", base))[0]
    return {"baseRecovery": base, "bands": validate_bands(value["bands"], project=False),
            "specialLight": special(value["specialLight"]),
            "forcedRecovery": percent(value["forcedRecovery"])}


def project_defaults() -> dict:
    return {"bands": deepcopy(DEFAULT_BANDS), "specialLight": dict(DEFAULT_SPECIAL),
            "forcedRecovery": 70.0}


def legacy_bands(value: dict) -> dict:
    """Translate the former fixed classes without changing their rule values."""
    bands = deepcopy(DEFAULT_BANDS)
    for row, limit, recovery in zip(bands,
            (value["lightLimit"], value["mediumLimit"], value["heavyLimit"], None),
            (value["lightRecovery"], value["mediumRecovery"],
             value["heavyRecovery"], value["overloadedRecovery"])):
        row.update(upper=limit, recovery=recovery)
    return {"bands": validate_bands(bands),
            "specialLight": {"enabled": True, "recovery": percent(value["ultralightRecovery"])},
            "forcedRecovery": percent(value["overloadedRecovery"])}


def native_projection(config) -> dict:
    return validate_native({
        "baseRecovery": config["baseRecovery"],
        "bands": [{key: entry[key] for key in ("upper", "movement", "recovery")}
                  for entry in validate_bands(config["bands"])],
        "specialLight": config["specialLight"], "forcedRecovery": config["forcedRecovery"],
    })


def split(value: list[dict], identity: int, at, *, new_id=None) -> tuple[list[dict], int]:
    bands = validate_bands(value)
    if len(bands) >= MAX_BANDS:
        raise ValueError(f"At most {MAX_BANDS} bands are supported")
    index = locate(bands, identity)
    lower = 0.0 if index == 0 else bands[index - 1]["upper"]
    upper = bands[index]["upper"]
    at = percent(at, positive=True)
    if at <= lower or (upper is not None and at >= upper):
        raise ValueError("The split must be strictly inside the selected band's load range")
    # IDs remain stable across insert/delete and are not array positions.
    if new_id is None:
        new_id = max(b["id"] for b in bands) + 1
    new = {**bands[index], "id": new_id}
    bands[index]["upper"] = at
    bands.insert(index + 1, new)
    return validate_bands(bands), new_id


def locate(bands, identity):
    if type(identity) is not int:
        raise ValueError("Invalid load-band identity")
    for index, row in enumerate(bands):
        if row["id"] == identity:
            return index
    raise ValueError("The selected load band no longer exists")


def merge(value, identity, neighbour, keep) -> tuple[list[dict], int]:
    """Delete one identity and give its combined range to the specified neighbour."""
    bands = validate_bands(value)
    if len(bands) == 1:
        raise ValueError("At least one band must remain")
    index = locate(bands, identity)
    other = locate(bands, neighbour)
    if abs(index - other) != 1:
        raise ValueError("Choose the immediately preceding or following band")
    if keep not in ("selected", "neighbour"):
        raise ValueError("Choose which band's properties survive")
    first, last = min(index, other), max(index, other)
    properties = bands[index] if keep == "selected" else bands[other]
    combined = {**properties, "id": neighbour, "upper": bands[last]["upper"]}
    bands[first:last + 1] = [combined]
    return validate_bands(bands), neighbour


def edit(value, identity, key, new_value) -> list[dict]:
    if key not in ("name", "upper", "movement", "recovery"):
        raise ValueError("This load-band property is not editable")
    bands = validate_bands(value)
    index = locate(bands, identity)
    if key == "upper" and index == len(bands) - 1:
        raise ValueError("The final band must have no upper limit")
    bands[index][key] = new_value
    return validate_bands(bands)


def runtime_rows(bands) -> list[tuple]:
    """Build domains shared by contiguous equal profiles, regardless of recovery."""
    bands = validate_bands(bands, project=False)
    result = []
    start = 0
    while start < len(bands):
        end = start
        while end + 1 < len(bands) and bands[end + 1]["movement"] == bands[start]["movement"]:
            end += 1
        lower = 0.0 if start == 0 else bands[start - 1]["upper"] / 100
        upper = bands[end]["upper"]
        span = 0.0 if upper is None or bands[start]["movement"] == 4 else upper / 100 - lower
        for band in bands[start:end + 1]:
            result.append((math.inf if band["upper"] is None else band["upper"] / 100,
                           band["movement"], band["recovery"] / 100, lower, span))
        start = end + 1
    return result


def evaluate(rules, load, special_active=False, forced=False) -> tuple[int, float, float]:
    """Reference model for native tests; runtime uses compiled assembly, not Python."""
    rules = validate_native(rules)
    rows = runtime_rows(rules["bands"])
    target = next((r for r in rows if math.isnan(load) or load <= r[0]), rows[-1])
    _, profile, recovery, lower, span = target
    fraction = max(0.0, min(1.0, (load - lower) / span)) if span and math.isfinite(load) else 0.0
    if forced:
        return 4, rules["forcedRecovery"] / 100, fraction
    if special_active and profile == 1 and rules["specialLight"]["enabled"]:
        return 0, rules["specialLight"]["recovery"] / 100, fraction
    return profile, recovery, fraction
