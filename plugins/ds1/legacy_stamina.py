"""Read-only migration of draft stamina settings; no balance preset is applied."""
from __future__ import annotations

from . import load_bands, stamina_patch

COMMON = {"enabled", "baseRecovery", "shieldRecovery", "encumbranceEnabled"}
FIXED_KEYS = COMMON | (set(stamina_patch.DEFAULT_RULES) - {"baseRecovery"})
BAND_KEYS = COMMON | {"nextBandId", "bands", "specialLight", "forcedRecovery"}


def parse(content: dict) -> dict:
    """Validate the exact historical schema and return its stored values."""
    if (type(content) is not dict or set(content) != {"schema", "stamina-rebalance"}
            or type(content["schema"]) is not int or content["schema"] not in (1, 2)):
        raise ValueError("Unsupported legacy stamina settings")
    value = content["stamina-rebalance"]
    expected = FIXED_KEYS if content["schema"] == 1 else BAND_KEYS
    if type(value) is not dict or set(value) != expected:
        raise ValueError("Legacy stamina settings do not match their schema version")
    if type(value["enabled"]) is not bool or type(value["encumbranceEnabled"]) is not bool:
        raise ValueError("Legacy switches must be on or off")
    bonus = value["shieldRecovery"]
    if type(bonus) not in (int, float) or not 0 <= bonus <= 100 or int(bonus) != bonus:
        raise ValueError("Legacy shield recovery must be a whole number from 0 to 100")
    base = stamina_patch.rate_value(value["baseRecovery"])
    if content["schema"] == 1:
        fixed = stamina_patch.validate_rules({key: value[key] for key in stamina_patch.DEFAULT_RULES})
        bands = {**load_bands.legacy_bands(fixed), "nextBandId": 5}
    else:
        validated = load_bands.validate_bands(value["bands"])
        identity = value["nextBandId"]
        if type(identity) is not int or not max(b["id"] for b in validated) < identity <= 2**31 - 1024:
            raise ValueError("Invalid legacy next load-band identity")
        bands = {"bands": validated, "nextBandId": identity,
                 "specialLight": load_bands.special(value["specialLight"]),
                 "forcedRecovery": load_bands.percent(value["forcedRecovery"])}
    return {**bands, "enabled": value["enabled"], "encumbranceEnabled": value["encumbranceEnabled"],
            "baseRecovery": base, "shieldRecovery": int(bonus)}
