"""Curated editor model for Story Mode's bounty-hunter dispatch response.

Only fields with a concrete owner in Rockstar's data are exposed.  The phase
graph is bounty-hunter-specific; cooldown and combat/loadout specs live in the
shared dispatch.meta and are reported with that scope made explicit.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
import re
import math
from decimal import Decimal, InvalidOperation
from pathlib import Path

try:
    from .paths import EXTRACT_ROOT
except ImportError:
    from paths import EXTRACT_ROOT


RESPONSE_SCALARS = (
    "RandomWeight", "MinBounty", "MaxLocationOverrideRadius",
    "MinDistanceToTown", "IdealSpawnDistanceToTown",
)
COOLDOWN_SECTIONS = (
    "DelayInGameHoursAfterBountyAcquired",
    "DelayInGameHoursAfterMyIncident",
    "DelayInGameHoursAfterMyIncidentTargetKilled",
)
LEVEL_LABELS = ("Clean", "Wanted 1", "Wanted 2", "Wanted 3", "Wanted 4+")
LEVEL_HELP = {
    "Clean": (
        "No active wanted/search level (internal wanted score 0). Arthur can "
        "still owe a regional bounty while this row applies."
    ),
    "Wanted 1": (
        "Rockstar wanted level 1: internal wanted score 1 through 4,999. "
        "This is pursuit severity, not bounty dollars."
    ),
    "Wanted 2": (
        "Rockstar wanted level 2: internal wanted score 5,000 through 14,999. "
        "This is pursuit severity, not bounty dollars."
    ),
    "Wanted 3": (
        "Rockstar wanted level 3: internal wanted score 15,000 through 24,999. "
        "This is pursuit severity, not bounty dollars."
    ),
    "Wanted 3+": (
        "Rockstar wanted level 3 or higher: internal wanted score 15,000 or "
        "more. This special row is used only for the target-undetected delay."
    ),
    "Wanted 4+": (
        "Rockstar wanted level 4 or higher: internal wanted score 25,000 or "
        "more. It also includes level 5, which starts at 100,000."
    ),
}
BOUNTY_PRESETS = ("BountyHunter", "BountyHunterShotgun", "BountyHunterSniper")
PRESENTATION_VERSION = 2

SETTING_PRESENTATION = {
    "RandomWeight": (
        "Response weight",
        "Relative selection weight against other eligible bounty responses. It is not a percentage or a time interval; larger values make this response more likely when the engine chooses among candidates.",
    ),
    "MinBounty": (
        "Minimum bounty (cents)",
        "Minimum total bounty required before this wilderness bounty-hunter response is eligible. The stored unit is cents, so 1200 means $12.00.",
    ),
    "MaxLocationOverrideRadius": (
        "Location override radius",
        "Maximum radius used by the response's location-override field. The data names the unit as a world-space distance, but the exact relocation formula has not been resolved; tune this cautiously in game.",
    ),
    "MinDistanceToTown": (
        "Minimum town distance",
        "Minimum world-space distance from a town before this wilderness response is eligible.",
    ),
    "IdealSpawnDistanceToTown": (
        "Ideal town distance",
        "Preferred world-space distance from a town used when the response chooses a spawn location. This is a target, not a guaranteed exact distance.",
    ),
}

COOLDOWN_PRESENTATION = {
    "DelayInGameHoursAfterBountyAcquired": (
        "After bounty acquired",
        "Random in-game-hour delay after the player acquires a bounty before another bounty-hunter response may be eligible.",
    ),
    "DelayInGameHoursAfterMyIncident": (
        "After hunter encounter",
        "Random in-game-hour delay after this bounty-hunter response owns an incident before it may run again.",
    ),
    "DelayInGameHoursAfterMyIncidentTargetKilled": (
        "After incident target killed",
        "Random in-game-hour delay used when this response's incident target was killed. The data does not expose a more specific player-facing condition.",
    ),
    "DelayInGameHoursAfterMyIncidentTargetUndetected": (
        "After target escaped detection",
        "In-game-hour delay after the incident target becomes undetected. Rockstar gates this row at WANTED_LEVEL3 and above.",
    ),
}

PHASE_LABELS = {
    "InitialRiders": "Initial riders",
    "OneStarBountyHunters": "Bounty tier 1",
    "TwoStarBountyHunters": "Bounty tier 2",
    "ThreeStarBountyHunters": "Bounty tier 3",
    "FourStarBountyHunters": "Bounty tier 4",
    "FiveStarBountyHunters": "Bounty tier 5",
}

PRESET_LABELS = {
    "BountyHunter": "Regular hunter",
    "BountyHunterShotgun": "Shotgun hunter",
    "BountyHunterSniper": "Sniper",
    "PoliceDog": "Police dog",
}

SCOPE_NOTE = (
    "Combat specs and loadouts are shared by ordinary law dispatch; they are "
    "shown read-only here so bounty-only edits do not silently retune every lawman."
)
MULTIPLIER_HELP = (
    "Engine GroupMultiplier for this phase. Rockstar's data does not document "
    "the exact group-size formula, so this remains a raw multiplier and should "
    "be tuned in game."
)


def ensure_bounty_hunter_metadata(data: dict) -> dict:
    """Backfill presentation fields at the API boundary.

    LEXEDITOR can stay open while its Python modules change.  A long-running
    process may therefore return an older payload shape to the current HTML.
    Keeping this normalizer public lets both the parser and server boundary
    guarantee the current schema, while the browser has its own checked-in
    presentation fallback for an already-running older process.
    """
    data["presentationVersion"] = PRESENTATION_VERSION
    data.setdefault("scopeNote", SCOPE_NOTE)
    for setting in data.get("settings", []):
        field = setting.get("field") or str(setting.get("id", "")).rsplit("/", 1)[-1]
        label, help_text = SETTING_PRESENTATION.get(field, (field.replace("_", " "), ""))
        setting.setdefault("label", label)
        setting.setdefault("help", help_text)
    for row in data.get("cooldowns", []):
        label, help_text = COOLDOWN_PRESENTATION.get(
            row.get("section"), (str(row.get("section", "Cooldown")).replace("_", " "), "")
        )
        row.setdefault("eventLabel", label)
        row.setdefault("help", help_text)
        row.setdefault("levelHelp", LEVEL_HELP.get(str(row.get("level", "")), ""))
    for phase in data.get("phases", []):
        name = str(phase.get("name", ""))
        phase.setdefault("label", PHASE_LABELS.get(name, name.replace("_", " ")))
        phase.setdefault("multiplierHelp", MULTIPLIER_HELP)
        for group in phase.get("groups", []):
            preset = str(group.get("preset", ""))
            group.setdefault("presetLabel", PRESET_LABELS.get(preset, preset.replace("_", " ")))
    for preset in data.get("presets", []):
        name = str(preset.get("preset", ""))
        preset.setdefault("label", PRESET_LABELS.get(name, name.replace("_", " ")))
    return data


def _parse(path: Path) -> ET.Element:
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    return ET.parse(path, parser=parser).getroot()


def _value(node: ET.Element | None) -> str | None:
    return node.get("value") if node is not None else None


def _phase(root: ET.Element, name: str) -> ET.Element | None:
    response = _one(root, "BountyResponses/BountyDispatch")
    return _find_named(_one(response, "DispatchPhases"), "Phase", name)


def _one(parent: ET.Element | None, path: str) -> ET.Element | None:
    for tag in path.split("/"):
        if parent is None:
            return None
        nodes = parent.findall(tag)
        if len(nodes) != 1:
            return None
        parent = nodes[0]
    return parent


def _scalar(node: ET.Element | None) -> ET.Element | None:
    return node if node is not None and set(node.attrib) == {"value"} and not len(node) and not (node.text or "").strip() else None


def _dispatch_group_rows(phase: ET.Element, phase_name: str) -> list[dict]:
    rows = []
    for bucket, xpath in (("fixed", "./DispatchPeds/DispatchPedGroups/DispatchGroup"),
                          ("random", "./DispatchPeds/RandomDispatchPedGroups/DispatchGroup")):
        for group in phase.findall(xpath):
            preset = (group.findtext("Preset") or "").strip()
            if not preset:
                continue
            prefix = f"phase/{phase_name}/{bucket}/{preset}"
            chance = group.find("./SelectionConditions/Condition[@type='CAIConditionRandom']/Chances")
            rows.append({
                "phase": phase_name,
                "bucket": bucket,
                "preset": preset,
                "presetLabel": PRESET_LABELS.get(preset, preset),
                "min": _value(group.find("MinNumPeds")),
                "max": _value(group.find("MaxNumPeds")),
                "weight": _value(group.find("RandomWeight")),
                "chance": _value(chance),
                "ids": {
                    "min": f"{prefix}/MinNumPeds",
                    "max": f"{prefix}/MaxNumPeds",
                    "weight": f"{prefix}/RandomWeight" if group.find("RandomWeight") is not None else None,
                    "chance": f"{prefix}/Chances" if chance is not None else None,
                },
            })
    return rows


def _find_named(parent: ET.Element | None, tag: str, name: str) -> ET.Element | None:
    if parent is None:
        return None
    items = [item for item in parent.findall(tag)
             if any((node.text or "").strip() == name for node in item.findall("Name"))]
    return items[0] if len(items) == 1 and _one(items[0], "Name") is not None else None


def _attach_vanilla_values(data: dict) -> None:
    """Attach exact update-layer references without requiring a staged dataset copy."""
    response_file = EXTRACT_ROOT / "dispatchresponses/wilderness/bountyhunters.meta"
    dispatch_file = EXTRACT_ROOT / "dispatch.meta"
    # This used to `return` silently when a reference extract was absent. The
    # result was that NO vanilla baseline was attached anywhere - settings,
    # cooldowns, phases and groups all lost theirs - and the editor simply showed
    # nothing, with no way to tell "vanilla equals this" from "vanilla is
    # unknown". It also made the #55 verifier die on `KeyError: 'vanilla'`, which
    # reads as a code defect rather than a missing extract.
    #
    # The degradation still happens - the values genuinely cannot be computed -
    # but it is now recorded so both the editor and the verifier can say why.
    missing = [str(path.relative_to(EXTRACT_ROOT))
               for path in (response_file, dispatch_file) if not path.exists()]
    data["vanillaUnavailable"] = missing
    if missing:
        return
    response_root, dispatch_root = _parse(response_file), _parse(dispatch_file)
    for setting in data["settings"]:
        target = _response_target(response_root, setting["id"])
        setting["vanilla"] = _value(target)
    for row in data["cooldowns"]:
        row["vanilla"] = {}
        for bound, edit_id in row["ids"].items():
            row["vanilla"][bound] = _value(_cooldown_target(dispatch_root, edit_id))
    for phase in data["phases"]:
        target = _response_target(response_root, phase["multiplierId"]) if phase["multiplierId"] else None
        phase["multiplierVanilla"] = _value(target)
        for group in phase["groups"]:
            group["vanilla"] = {}
            for field, edit_id in group["ids"].items():
                group["vanilla"][field] = _value(_response_target(response_root, edit_id)) if edit_id else None


def read_bounty_hunters(response_file: Path, dispatch_file: Path) -> dict:
    response_root, dispatch_root = _parse(response_file), _parse(dispatch_file)
    response = response_root.find("./BountyResponses/BountyDispatch")
    if response is None or (response.findtext("Name") or "").strip() != "LAW_BOUNTY_HUNTERS_CSI":
        raise ValueError("bountyhunters.meta does not contain LAW_BOUNTY_HUNTERS_CSI")

    settings = []
    for tag in RESPONSE_SCALARS:
        value = _value(response.find(tag))
        if value is not None:
            label, help_text = SETTING_PRESENTATION[tag]
            settings.append({"id": f"response/{tag}", "field": tag, "value": value,
                             "label": label, "help": help_text})

    phases = []
    for phase in response.findall("./DispatchPhases/Phase"):
        name = (phase.findtext("Name") or "").strip()
        if not name:
            continue
        phases.append({
            "name": name,
            "label": PHASE_LABELS.get(name, name),
            "multiplier": _value(phase.find("GroupMultiplier")),
            "multiplierId": f"phase/{name}/GroupMultiplier" if phase.find("GroupMultiplier") is not None else None,
            "multiplierHelp": MULTIPLIER_HELP,
            "groups": _dispatch_group_rows(phase, name),
        })

    cooldown = _find_named(dispatch_root.find("BountyResponseCooldowns"), "Item",
                           "BountyHuntersGlobalCooldown")
    cooldown_rows = []
    if cooldown is not None:
        for section in COOLDOWN_SECTIONS:
            group = cooldown.find(section)
            if group is None:
                continue
            for index, item in enumerate(group.findall("Item")):
                values = {}
                ids = {}
                for bound in ("Min", "Max"):
                    value = _value(item.find(bound))
                    if value is not None:
                        values[bound.lower()] = value
                        ids[bound.lower()] = f"cooldown/{section}/{index}/{bound}"
                label, help_text = COOLDOWN_PRESENTATION[section]
                level = LEVEL_LABELS[index] if index < len(LEVEL_LABELS) else str(index)
                cooldown_rows.append({"section": section, "eventLabel": label,
                                      "help": help_text,
                                      "level": level,
                                      "levelHelp": LEVEL_HELP.get(level, ""),
                                      **values, "ids": ids})
        undetected = cooldown.find("DelayInGameHoursAfterMyIncidentTargetUndetected")
        if undetected is not None and _value(undetected.find("Min")) is not None:
            section = "DelayInGameHoursAfterMyIncidentTargetUndetected"
            label, help_text = COOLDOWN_PRESENTATION[section]
            cooldown_rows.append({"section": section, "eventLabel": label,
                                  "help": help_text, "level": "Wanted 3+",
                                  "levelHelp": LEVEL_HELP["Wanted 3+"],
                                  "min": _value(undetected.find("Min")),
                                  "ids": {"min": "cooldown/DelayInGameHoursAfterMyIncidentTargetUndetected/0/Min"}})

    presets = []
    preset_root = dispatch_root.find("DispatchPedGroupPresets")
    spec_root = dispatch_root.find("DispatchCombatSpecs")
    for preset_name in BOUNTY_PRESETS:
        preset = next((x for x in preset_root.findall("DispatchGroup")
                       if x.get("key") == preset_name), None) if preset_root is not None else None
        if preset is None:
            continue
        spec_name = (preset.findtext("CombatSpec") or "").strip()
        spec = _find_named(spec_root, "Spec", spec_name)
        presets.append({
            "preset": preset_name,
            "label": PRESET_LABELS.get(preset_name, preset_name),
            "combatSpec": spec_name,
            "vehicleSet": (preset.findtext("VehicleSet") or "").strip(),
            "combatInfo": (spec.findtext("CombatInfo") or "").strip() if spec is not None else "",
            "chaseProfile": (spec.findtext("MountedChasingProfileOverride") or "").strip() if spec is not None else "",
            "loadouts": [{"name": (x.findtext("LoadoutName") or "").strip(),
                           "weight": _value(x.find("RandomWeight"))}
                          for x in spec.findall("./Loadouts/Item")] if spec is not None else [],
        })

    data = {"available": True, "responseFile": str(response_file), "dispatchFile": str(dispatch_file),
            "settings": settings, "cooldowns": cooldown_rows, "phases": phases,
            "presets": presets,
            "scopeNote": SCOPE_NOTE}
    _attach_vanilla_values(data)
    values = [(row["id"], row["value"]) for row in settings]
    values += [(identity, row.get(key)) for row in cooldown_rows for key, identity in row["ids"].items()]
    for phase in phases:
        if phase["multiplierId"]:
            values.append((phase["multiplierId"], phase["multiplier"]))
        values += [(identity, group.get(key)) for group in phase["groups"] for key, identity in group["ids"].items() if identity]
    data["readonlyIds"] = []
    for identity, value in values:
        target = _response_target(response_root, identity) if not identity.startswith("cooldown/") else _cooldown_target(dispatch_root, identity)
        try:
            if target is None:
                raise ValueError("Unsupported source")
            _numeric(value, identity, maximum=1.0 if identity.endswith("/Chances") else None)
        except ValueError:
            data["readonlyIds"].append(identity)
    return ensure_bounty_hunter_metadata(data)


def _numeric(value: object, field: str, minimum: float = 0.0, maximum: float | None = None) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError(f"{field} must be numeric")
    text = str(value).strip()
    text_num = text[:-1] if text.lower().endswith("f") else text
    if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", text_num):
        raise ValueError(f"{field} must be numeric")
    try:
        number = Decimal(text_num)
    except InvalidOperation as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if not number.is_finite() or not math.isfinite(float(text_num)):
        raise ValueError(f"{field} must be finite")
    if number < Decimal(str(minimum)) or (maximum is not None and number > Decimal(str(maximum))):
        limit = f" between {minimum:g} and {maximum:g}" if maximum is not None else f" at least {minimum:g}"
        raise ValueError(f"{field} must be{limit}")
    return text


def _response_target(root: ET.Element, edit_id: str) -> ET.Element | None:
    parts = edit_id.split("/")
    response = _one(root, "BountyResponses/BountyDispatch")
    name = _one(response, "Name")
    if response is None or name is None or (name.text or "").strip() != "LAW_BOUNTY_HUNTERS_CSI":
        return None
    if len(parts) == 2 and parts[0] == "response" and parts[1] in RESPONSE_SCALARS:
        return _scalar(_one(response, parts[1]))
    if len(parts) == 3 and parts[0] == "phase" and parts[2] == "GroupMultiplier":
        phase = _phase(root, parts[1])
        return _scalar(_one(phase, "GroupMultiplier"))
    if len(parts) == 5 and parts[0] == "phase" and parts[2] in {"fixed", "random"}:
        phase = _phase(root, parts[1])
        if phase is None:
            return None
        container = _one(phase, "DispatchPeds/DispatchPedGroups" if parts[2] == "fixed" else "DispatchPeds/RandomDispatchPedGroups")
        groups = [g for g in container.findall("DispatchGroup") if any((node.text or "").strip() == parts[3] for node in g.findall("Preset"))] if container is not None else []
        group = groups[0] if len(groups) == 1 and _one(groups[0], "Preset") is not None else None
        if group is None:
            return None
        if parts[4] == "Chances":
            conditions = _one(group, "SelectionConditions")
            matches = conditions.findall("Condition[@type='CAIConditionRandom']") if conditions is not None else []
            return _scalar(_one(matches[0], "Chances")) if len(matches) == 1 else None
        if parts[4] in {"MinNumPeds", "MaxNumPeds", "RandomWeight"}:
            return _scalar(_one(group, parts[4]))
    return None


def _cooldown_target(root: ET.Element, edit_id: str) -> ET.Element | None:
    parts = edit_id.split("/")
    if len(parts) != 4 or parts[0] != "cooldown" or parts[3] not in {"Min", "Max"}:
        return None
    if parts[1] not in (*COOLDOWN_SECTIONS, "DelayInGameHoursAfterMyIncidentTargetUndetected") or not re.fullmatch(r"0|[1-9][0-9]*", parts[2]):
        return None
    cooldown = _find_named(_one(root, "BountyResponseCooldowns"), "Item", "BountyHuntersGlobalCooldown")
    group = _one(cooldown, parts[1])
    if group is None:
        return None
    if parts[1] == "DelayInGameHoursAfterMyIncidentTargetUndetected":
        return _scalar(_one(group, parts[3])) if parts[2] == "0" else None
    try:
        item = group.findall("Item")[int(parts[2])]
    except (ValueError, IndexError):
        return None
    return _scalar(_one(item, parts[3]))


def prepare_bounty_hunter_edits(response_file: Path, dispatch_file: Path, edits: list[dict]) -> tuple[int, list[tuple[Path, ET.Element]]]:
    """Validate a candidate batch without writing either file or its backup."""
    if not isinstance(edits, list):
        raise ValueError("Bounty-hunter edits must be a list")
    if not edits:
        return 0, []
    response_root, dispatch_root = _parse(response_file), _parse(dispatch_file)
    response_changed = dispatch_changed = 0
    seen = set()
    for edit in edits:
        if not isinstance(edit, dict) or set(edit) != {"id", "value"}:
            raise ValueError("Bounty-hunter edits require only id and value")
        edit_id = edit["id"]
        if not isinstance(edit_id, str):
            raise ValueError("Bounty-hunter setting id must be text")
        if not edit_id or edit_id in seen:
            raise ValueError(f"duplicate or empty bounty-hunter setting id: {edit_id!r}")
        seen.add(edit_id)
        target = _response_target(response_root, edit_id)
        is_chance = edit_id.endswith("/Chances")
        value = _numeric(edit.get("value", ""), edit_id, maximum=1.0 if is_chance else None)
        if target is not None:
            _numeric(target.get("value"), edit_id, maximum=1.0 if is_chance else None)
            target.set("value", value); response_changed += 1; continue
        target = _cooldown_target(dispatch_root, edit_id)
        if target is not None:
            _numeric(target.get("value"), edit_id)
            target.set("value", value); dispatch_changed += 1; continue
        raise ValueError(f"unknown or unavailable bounty-hunter setting: {edit_id}")

    # Reject impossible min/max ranges before either file is written.
    for identity in seen:
        prefix, field = identity.rsplit('/', 1)
        pair = {'Min': ('Min', 'Max'), 'Max': ('Min', 'Max'), 'MinNumPeds': ('MinNumPeds', 'MaxNumPeds'), 'MaxNumPeds': ('MinNumPeds', 'MaxNumPeds')}.get(field)
        if pair is None:
            continue
        lookup, doc = (_cooldown_target, dispatch_root) if identity.startswith('cooldown/') else (_response_target, response_root)
        nodes = [lookup(doc, f'{prefix}/{bound}') for bound in pair]
        # The undetected cooldown intentionally has only Min.
        if prefix == 'cooldown/DelayInGameHoursAfterMyIncidentTargetUndetected/0' and field == 'Min':
            continue
        if any(node is None for node in nodes):
            raise ValueError(f'{identity}: range boundaries are unavailable or ambiguous')
        values = [_numeric(node.get('value'), identity) for node in nodes]
        if Decimal(values[0].rstrip('fF')) > Decimal(values[1].rstrip('fF')):
            raise ValueError(f'{identity}: minimum exceeds maximum')
    prepared = []
    if response_changed:prepared.append((response_file, response_root))
    if dispatch_changed:prepared.append((dispatch_file, dispatch_root))
    return response_changed + dispatch_changed, prepared
