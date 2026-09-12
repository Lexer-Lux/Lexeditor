"""Project Zomboid Data Map assembled from current structured adapters."""
from __future__ import annotations

from pathlib import Path

from . import core, craftrecipe, evolvedrecipe, fixing, fluid, mannequin, model, sound, timedaction, vehicle, zedscript


def read(root: Path) -> dict:
    root = root.resolve()
    base = core.data_map(root)
    rows = [row for row in base.get("rows", []) if not row.get("filename", "").endswith(".txt")]

    items = core.read_items(root)
    evolved = evolvedrecipe.read(root)
    crafts = craftrecipe.read(root)
    fixings = fixing.read(root)
    fluids = fluid.read(root)
    vehicles = vehicle.read(root)
    sounds = sound.read(root)
    models = model.read(root)
    mannequins = mannequin.read(root)
    timed_actions = timedaction.read(root)
    inventory = zedscript.inventory(root)
    by_path: dict[str, set[str]] = {}
    for row in inventory["rows"]:
        by_path.setdefault(row["path"], set()).add(row["kind"])
    item_paths = {row["path"] for row in items["rows"]}
    evolved_paths = {row["path"] for row in evolved["rows"]}
    craft_paths = {row["path"] for row in crafts["rows"]}
    fixing_paths = {row["path"] for row in fixings["rows"]}
    fluid_paths = {row["path"] for row in fluids["rows"]}
    vehicle_paths = {row["path"] for row in vehicles["rows"]}
    sound_paths = {row["path"] for row in sounds["rows"]}
    model_paths = {row["path"] for row in models["rows"]}
    mannequin_paths = {row["path"] for row in mannequins["rows"]}
    timed_action_paths = {row["path"] for row in timed_actions["rows"]}
    errors = {
        row["path"] for result in (items, evolved, crafts, fixings, fluids, vehicles, sounds, models, mannequins, timed_actions, inventory)
        for row in result.get("errors", []) if isinstance(row, dict) and row.get("path")
    }

    for path in core.script_paths(root):
        relative = path.relative_to(root).as_posix()
        editors = []
        if relative in item_paths:
            editors.append("Items")
        if relative in evolved_paths:
            editors.append("Evolved Recipes")
        if relative in craft_paths:
            editors.append("Craft Recipes")
        if relative in fixing_paths:
            editors.append("Fixing")
        if relative in fluid_paths:
            editors.append("Fluids")
        if relative in vehicle_paths:
            editors.append("Vehicles")
        if relative in sound_paths:
            editors.append("Sounds")
        if relative in model_paths:
            editors.append("Models")
        if relative in mannequin_paths:
            editors.append("Mannequins")
        if relative in timed_action_paths:
            editors.append("Timed Actions")
        kinds = sorted(by_path.get(relative, set()), key=str.casefold)
        if relative in errors:
            status = "partial" if editors else "recognized"
            notes = "At least one structured parser failed closed; affected data remains untouched."
        elif editors:
            status = "partial"
            notes = "Structured editors: " + ", ".join(editors) + ". Other record families and unmodeled fields are preserved."
        else:
            status = "recognized"
            notes = "Recognized Build 42 script families: " + (", ".join(kinds) if kinds else "none currently modeled") + "."
        rows.append({
            "filename": relative,
            "status": status,
            "editor": ", ".join(editors),
            "notes": notes,
        })

    rows.sort(key=lambda row: row.get("filename", "").casefold())
    return {"rows": rows}
