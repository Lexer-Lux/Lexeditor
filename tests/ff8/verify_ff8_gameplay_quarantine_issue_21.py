"""Regression contract for visible FF8 Tweak persistence after crash repair.

The quarantine is that nothing is accepted and written to the game without
also being visible and editable in the Tweaks page. Every gameplay tweak is a
tweak mod now, so the rule is checked on that model: every tweak mod in the
library is listed with its settings, the page draws a panel for every listed
mod and a control for every setting it does not hand to another screen, save
accepts nothing else, and what is saved is what loads back.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests.shared.plugin_ui import plugin_ui

from core import script_mods
from plugins.ff8 import gameplay_settings, paths, runtime_layout


# Every switch the Tweaks page showed before tweaks became mods, and the
# library tweak mod (or mod setting) that carries it now. None may disappear.
VISIBLE = {
    "flyingEvaEnabled": ("flying-eva", None), "autoSortInventory": ("auto-sort-inventory", None),
    "autoSortMagic": ("auto-sort-magic", None), "enhancedAbilityMenu": ("enhanced-ability-menu", None),
    "singleGf": ("monogamy", None), "universalItem": ("battle-shortcuts", "universalItem"),
    "scannedTargetScan": ("battle-shortcuts", "scannedTargetScan"),
    "partySwitch": ("battle-shortcuts", "partySwitch"),
    "drawOncePerEnemy": ("draw-and-card", "drawOncePerEnemy"),
    "streamlinedDraw": ("draw-and-card", "streamlinedDraw"), "betterCard": ("draw-and-card", "betterCard"),
    "formulaeRework": ("formulae-rework", None), "fixedCommandMenu": ("command-menu-rework", None),
    "trueAtbWait": ("true-atb-wait", None), "modernControls": ("modern-controls", None),
    "vibrationConsolidation": ("vibration-rationalization", None),
    "betterTargeting": ("better-targeting", None), "damageLimitRemoval": ("remove-damage-limit", None),
    "fastStart": ("fast-start", None), "xpBars": ("xp-bars", None), "hpBars": ("hp-bars", None),
    "flatStatAbilities": ("flat-stat-abilities", None), "maxSpellEnabled": ("max-spell", None),
    "gfHpBars": ("gf-mp-bars", None), "noMagicConsumption": ("no-magic-consumption", None),
    "dropsAfterMug": ("drops-after-mug", None),
}
# Project features that stay on the page beside the tweak mods.
PAGE_PANELS = ("GF SPELLBOOKS", "SHARED PARTY MAGIC INVENTORY")
TWEAK = '''
def build(settings, context):
    return {context.HEXT + "/%s.txt": "".join(f"# {k}={v}\\n" for k, v in sorted(settings.items())) or "# on\\n"}
'''


def make(library: Path, mod_id: str, name: str, schema: dict) -> Path:
    root = library / name
    (root / "script").mkdir(parents=True)
    (root / "script" / "__init__.py").write_text("", encoding="utf-8")
    (root / "script" / "tweak.py").write_text(TWEAK % mod_id, encoding="utf-8")
    (root / "settings.schema.json").write_text(json.dumps(schema), encoding="utf-8")
    (root / "mod.json").write_text(json.dumps({"id": mod_id, "name": name, "enabled": False,
                                               "script": {"version": 1}}), encoding="utf-8")
    script_mods.set_trusted(root, True)
    return root


def check_persistence() -> None:
    with tempfile.TemporaryDirectory(prefix="ff8-quarantine-") as temporary:
        temp = Path(temporary)
        previous = os.environ.get(script_mods.TRUST_ENV)
        os.environ[script_mods.TRUST_ENV] = str(temp / "trust.json")
        try:
            project, game = temp / "project", temp / "game"
            library = project / ".lexeditor-mods"
            game.mkdir()
            make(library, "monogamy", "Monogamy", {"title": "MONOGAMY", "fields": []})
            make(library, "battle-shortcuts", "Battle Shortcuts", {"title": "BATTLE SHORTCUTS", "fields": [
                {"key": "universalItem", "label": "Universal Item", "type": "bool", "default": True},
                {"key": "partySwitch", "label": "FF10-style Party Switch", "type": "bool", "default": False}]})
            make(library, "formulae-rework", "Formulae Rework", {"title": "FORMULAE REWORK", "fields": []})
            make(library, "max-spell", "Max Spell", {"title": "MAX SPELL", "fields": [
                {"key": "limit", "label": "Maximum stock", "type": "int", "default": 100, "min": 1, "max": 255}]})

            loaded = gameplay_settings.load(project, game)
            listed = {row["id"]: row for row in loaded["tweaks"]}
            assert set(listed) == {"monogamy", "battle-shortcuts", "formulae-rework", "max-spell"}, listed
            assert all(row["enabled"] is False for row in listed.values())
            assert listed["battle-shortcuts"]["values"] == {"universalItem": True, "partySwitch": False}

            everything = {mod_id: {"enabled": True} for mod_id in listed}
            everything["battle-shortcuts"]["values"] = {"partySwitch": True}
            everything["max-spell"]["values"] = {"limit": 200}
            gameplay_settings.save({"tweaks": everything, "gfSpellbooksEnabled": True,
                                    "sharedMagicInventory": True}, game_root=game, project_root=project)
            loaded = gameplay_settings.load(project, game)
            for row in loaded["tweaks"]:
                assert row["enabled"] is True, row["id"]
            values = {row["id"]: row["values"] for row in loaded["tweaks"]}
            assert values["battle-shortcuts"] == {"universalItem": True, "partySwitch": True}
            assert values["max-spell"] == {"limit": 200}
            assert loaded["gfSpellbooksEnabled"] is True and loaded["sharedMagicInventory"] is True
            assert loaded["singleGf"] is True

            # Disabling a supported tweak must preserve vanilla behavior too:
            # its switch reads back off and its patch leaves the composed runtime.
            runtime = project / ".lexeditor-runtime"
            composed = gameplay_settings.materialized_tweak_patches(runtime, {"formulae-rework"})
            assert len(composed) == 1 and composed[0].is_file(), composed
            composed = composed[0]
            gameplay_settings.save({"tweaks": {"formulae-rework": {"enabled": False}}},
                                   game_root=game, project_root=project)
            loaded = gameplay_settings.load(project, game)
            assert next(row for row in loaded["tweaks"] if row["id"] == "formulae-rework")["enabled"] is False
            assert not composed.exists()

            # Nothing outside the listed tweaks and their schemas is accepted.
            for bad in ({"tweaks": {"not-listed": {"enabled": True}}},
                        {"tweaks": {"monogamy": {"enabled": True, "hidden": 1}}},
                        {"tweaks": {"max-spell": {"values": {"unknownKey": 1}}}},
                        {"tweaks": {"max-spell": {"values": {"limit": 999}}}},
                        {"tweaks": {"monogamy": {"enabled": "true"}}}):
                try:
                    gameplay_settings.save(bad, game_root=game, project_root=project)
                except ValueError:
                    pass
                else:
                    raise AssertionError(f"save accepted {bad}")
            assert {row["id"]: row["values"] for row in gameplay_settings.load(project, game)["tweaks"]} == values
        finally:
            if previous is None:
                os.environ.pop(script_mods.TRUST_ENV, None)
            else:
                os.environ[script_mods.TRUST_ENV] = previous


def check_editor() -> str:
    editor = plugin_ui('ff8')
    rendered = editor[editor.index("function renderGameplaySettings(){"):
                      editor.index('const settingsView=LexeditorUI.settingsColumns(panels')]
    # One panel per listed tweak mod, titled from its schema, switch named after it.
    assert "const panels=rows.map(row=>{" in rendered
    assert '"aria-label":row.name' in rendered
    assert "panel(schema.title||row.name.toUpperCase(),schema.help,toggle,body,blocker)" in rendered
    # Every setting a mod does not hand to another screen gets a control here.
    assert "schema.fields.filter(field=>!field.hidden).map(field=>tweakField(row,field))" in rendered
    # Availability diagnostics remain attached to the visible tweak control.
    assert 'LexeditorUI.badge("NOT AVAILABLE YET",{tone:"warning",title:blocker})' in rendered
    assert "disabled:Boolean(blocker)&&!row.enabled" in rendered
    for title in PAGE_PANELS:
        assert f'panel("{title}"' in rendered, title
    # The save payload carries exactly what the page edits.
    assert ("return {gfSpellbooksEnabled:settings.gfSpellbooksEnabled,"
            "sharedMagicInventory:settings.sharedMagicInventory,tweaks};") in editor
    return editor


def check_library(editor: str) -> str:
    """The reader's library, when installed: nothing that was visible is gone."""
    library = Path(paths.MODS_ROOT)
    if not library.is_dir():
        return f"library skipped: {library} is not installed"
    mods = {row["id"]: Path(row["path"]) for row in runtime_layout.catalog(paths.PROJECT_ROOT, library)
            if not row.get("selected") and script_mods.is_script_mod(Path(row["path"]))}
    missing = []
    for key, (mod_id, setting) in VISIBLE.items():
        if mod_id not in mods:
            missing.append(f"{key} -> {mod_id}")
            continue
        fields = {field["key"]: field for field in script_mods.schema(mods[mod_id])["fields"]}
        if setting is not None and (setting not in fields or fields[setting].get("hidden")):
            missing.append(f"{key} -> {mod_id}.{setting}")
    assert not missing, f"visible tweaks lost from the library: {missing}"
    # A hidden setting must be edited on another screen.
    for mod_id, root in mods.items():
        for field in script_mods.schema(root)["fields"]:
            if field.get("hidden"):
                assert f'tweakValues("{mod_id}").{field["key"]}' in editor, f"{mod_id}.{field['key']} is not editable anywhere"
    return f"library checked: {len(mods)} tweak mods"


def main() -> None:
    check_persistence()
    editor = check_editor()
    print(check_library(editor))
    print("FF8 visible Tweak persistence regression check passed")


if __name__ == "__main__":
    main()
