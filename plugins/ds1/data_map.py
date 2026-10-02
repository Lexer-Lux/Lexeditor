"""Honest parameter coverage for the shared Data Map."""
from .formats import SUBTABS, EFFECT_TABLE


def build(document, source):
    rows = []
    for filename in document.members:
        table = filename.removesuffix(".param")
        targets = [{"id": sub, "label": label} for sub, label, name in SUBTABS if name == table]
        if table == "NpcParam":
            targets = [{"id": "enemies", "label": "Enemies"}]
        elif table == EFFECT_TABLE:
            targets = [{"id": "effects-all", "label": "Effects"}]
        editable = [f for f in document.schemas.get(table, {}).get("fields", []) if f["editable"]]
        structured = bool(targets and editable)
        rows.append({
            "id": filename, "filename": filename, "path": str(source) + " / " + filename,
            "controls": "Buffs, debuffs and equipment passives" if table == EFFECT_TABLE else table,
            "status": "partial" if structured else "not-integrated",
            "coverage": "structured" if structured else "unavailable",
            "sourceAvailable": True, "openable": structured,
            "targets": targets if structured else [],
            "notes": (f"{len(editable)} documented properties are editable. "
                      "Other properties and unknown bytes are preserved."
                      if structured else "Preserved in the archive. No complete editing interface is available."),
        })
    if EFFECT_TABLE not in document.params:
        rows.append({"id": "effects-missing", "filename": EFFECT_TABLE + ".param",
                     "controls": "Buffs, debuffs and equipment passives",
                     "status": "not-integrated", "coverage": "unavailable",
                     "sourceAvailable": False, "openable": False,
                     "notes": "Open a complete Remastered parameter archive to edit effects."})
    rows.append({"id": "native-rules", "filename": "DarkSoulsRemastered.exe",
                 "controls": "Native rules, including base stamina recovery",
                 "status": "not-integrated", "coverage": "unavailable",
                 "sourceAvailable": False, "openable": False,
                 "notes": "The effects editor does not change native code or equip-load thresholds."})
    return {"rows": rows}
