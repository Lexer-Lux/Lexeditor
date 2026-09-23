"""Truthful Factorio Data Map for the JSON-import / override-mod workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Any


# These rows describe edit coverage, not merely data that happens to be present.
# "partial" means the source family contains substantially more fields than the
# semantic controls Lexeditor currently writes.
BASE_ROWS = (
    {
        "filename": "source/data-raw-dump.json",
        "controls": "Factorio data.raw snapshot produced by the game's --dump-data command.",
        "notes": "Read-only import. Lexeditor never evaluates the Lua source mods that produced it.",
        "status": "partial", "coverage": "structured", "target": "recipes", "openable": True,
    },
    {
        "filename": "source/mod-list.json",
        "controls": "Enabled source-mod names used only to preserve late override load order.",
        "notes": "Read-only metadata. Optional dependencies are generated for enabled mods; the source list is never modified.",
        "status": "partial", "coverage": "structured", "target": "info", "openable": True,
    },
    {
        "filename": "data.raw.recipe",
        "controls": "Recipes: enabled state, crafting time and maximum productivity.",
        "notes": "Ingredients, products, icons, localization and advanced recipe properties remain visible reference data but are not rewritten.",
        "status": "partial", "coverage": "structured", "target": "recipes", "openable": True,
    },
    {
        "filename": "data.raw.<ItemPrototype>",
        "controls": "ItemPrototype descendants: stack size with not-stackable validation.",
        "notes": "Item identity, placement, fuel, spoilage, icons and subtype-specific fields remain source-only.",
        "status": "partial", "coverage": "structured", "target": "items", "openable": True,
    },
    {
        "filename": "data.raw.assembling-machine / furnace / rocket-silo",
        "controls": "Crafting machines, furnaces and rocket silos: crafting speed; categories, energy use and module slots are shown as references.",
        "notes": "Entity graphics, energy sources, fluid boxes, effects and subtype-specific fields are not rewritten.",
        "status": "partial", "coverage": "structured", "target": "machines", "openable": True,
    },
    {
        "filename": "data.raw.technology",
        "controls": "Technologies: enabled state, validated prerequisite technologies, fixed unit count and research time.",
        "notes": "Count-formula technologies keep formula-controlled counts read-only. Effects/science packs are shown as reference data.",
        "status": "partial", "coverage": "structured", "target": "technologies", "openable": True,
    },
    {
        "filename": "overrides.json",
        "controls": "Lexeditor-owned structured edit delta keyed by real prototype type/name identity.",
        "notes": "Saved atomically beside the immutable source snapshot; never copied over a source mod.",
        "status": "integrated", "coverage": "structured", "target": "info", "openable": True,
    },
    {
        "filename": "build/<name>_<version>.zip",
        "controls": "Deterministic Factorio mod package containing info.json and generated data-final-fixes.lua.",
        "notes": "Uses Factorio's native mod loader. Generated Lua contains typed assignments only; no user/source Lua is copied or executed.",
        "status": "integrated", "coverage": "structured", "target": "info", "openable": True,
    },
    {
        "filename": "data.raw.fluid",
        "controls": "Fluid identities are indexed for recipe-reference diagnostics only.",
        "notes": "No dedicated fluid property editor or writer is connected.",
        "status": "not-integrated", "coverage": "unavailable", "target": None, "openable": False,
    },
    {
        "filename": "data.raw.recipe-category",
        "controls": "Recipe-category identities are indexed for recipe/machine reference diagnostics.",
        "notes": "No category creation or property editor is connected.",
        "status": "not-integrated", "coverage": "unavailable", "target": None, "openable": False,
    },
    {
        "filename": "other data.raw prototype types",
        "controls": "Entities, tiles, equipment, achievements, utility constants and other prototype families.",
        "notes": "Preserved in the source dump and untouched by export. They need family-specific semantic editors before Lexeditor may write them.",
        "status": "not-integrated", "coverage": "unavailable", "target": None, "openable": False,
    },
    {
        "filename": "settings.lua / settings-updates.lua / settings-final-fixes.lua",
        "controls": "Factorio settings prototype stage.",
        "notes": "Not executed or rewritten by Lexeditor. This plugin starts from the post-load JSON prototype snapshot.",
        "status": "not-integrated", "coverage": "unavailable", "target": None, "openable": False,
    },
    {
        "filename": "data.lua / data-updates.lua",
        "controls": "Earlier Factorio prototype-stage Lua from source mods.",
        "notes": "Never executed by Lexeditor. The generated override runs separately in data-final-fixes.lua after declared/optional dependencies.",
        "status": "not-integrated", "coverage": "unavailable", "target": None, "openable": False,
    },
    {
        "filename": "control.lua / runtime scripts",
        "controls": "Factorio runtime scripting and events.",
        "notes": "Outside this data-stage editor. Lexeditor does not execute or rewrite runtime Lua.",
        "status": "not-integrated", "coverage": "unavailable", "target": None, "openable": False,
    },
)


def build_data_map(project: Path, *, counts: dict[str, int] | None = None,
                   diagnostics: list[dict[str, Any]] | None = None,
                   unsupported_prototypes: dict[str, int] | None = None) -> dict[str, Any]:
    rows = [dict(row) for row in BASE_ROWS]
    discovered = []
    for prototype_type, record_count in sorted(
            (unsupported_prototypes or {}).items(), key=lambda item: item[0].casefold()):
        discovered.append({
            "filename": f"data.raw.{prototype_type}",
            "controls": "Prototype family present in the imported data.raw snapshot.",
            "notes": "Visible because this family exists in the imported dump. No semantic editor is connected; export preserves it untouched.",
            "status": "not-integrated", "coverage": "unavailable",
            "target": None, "openable": False, "records": int(record_count),
        })
    if discovered:
        catch_all = next(
            (index for index, row in enumerate(rows)
             if row["filename"] == "other data.raw prototype types"),
            len(rows),
        )
        rows[catch_all:catch_all] = discovered
    counts = counts or {}
    for row in rows:
        target = row.get("target")
        if target in {"recipes", "items", "machines", "technologies"}:
            row["records"] = int(counts.get(target, 0))
    problems = diagnostics or []
    return {
        "rows": rows,
        "summary": {
            "project": str(Path(project).resolve()),
            "integrated": sum(row["status"] == "integrated" for row in rows),
            "partial": sum(row["status"] == "partial" for row in rows),
            "notIntegrated": sum(row["status"] == "not-integrated" for row in rows),
            "diagnostics": len(problems),
        },
    }
