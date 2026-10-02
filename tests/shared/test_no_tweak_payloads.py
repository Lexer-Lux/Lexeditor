"""Tweaks live in the mod library, never in Lexeditor's repository.

A tweak is an ordinary mod: its script, ASI, Hext, DLL or INI travels with the
mod that owns it, under the reader's mod library. This check fails when tweak
code or a built tweak payload is committed here, and when an allowance below
outlives the thing it allowed, so the list can only shrink.
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]

# Built payloads a game loads as a tweak. Hext text is recognised by its
# folder, since FFNx reads plain .txt files from hext/.
TWEAK_SUFFIXES = (".asi", ".hext")
TWEAK_FOLDERS = ("hext", "native_runtime", "GameplayTweaks")

# Binaries that may stay, each with the reason. A driver or a third-party
# runtime is plugin infrastructure, not a tweak; the rest wait on their issue.
ALLOWED_BINARIES = {
    "plugins/ff8/ffnx_issue_51/package/AF3DN.P": "FFNx derivative driver (plugin infrastructure)",
    "plugins/ff8/ffnx_issue_51/package/FFNx_steam_api.dll": "FFNx derivative driver (plugin infrastructure)",
    "plugins/ff9/runtime/Memoria.Scripts.Lexeditor.dll": "FF9 tweaks, moving to library mods in #913",
}
# Folders holding tweak source that has not moved yet.
ALLOWED_FOLDERS = {
    "plugins/ff7r/native_runtime": "FF7R runtime tweaks, moving to library mods in #912",
}
# Asset build tools and editors that ship as binaries but never load into a game.
TOOL_PREFIXES = ("tools/", "plugins/rdr2/assets/item-icons/")
# Tweak code that moved into tweak mods. A module of the same name coming back
# into a plugin is a tweak left behind or re-added.
MOVED_TWEAK_MODULES = {
    "ff8": {
        "battle_issue_54", "battle_results_issue_466", "battle_shortcuts", "better_card",
        "better_targeting_issue_64", "character_growth", "damage_limit", "drop_chance",
        "fast_start", "fixed_command_menu", "flat_stat_abilities", "flying_eva",
        "formulae_rework", "gf_acquisition_rework", "gf_hp_casting", "gf_hp_casting_asm",
        "gf_hp_casting_code", "healing_rework", "hit_frame_log", "inventory_auto_sort",
        "luck_accuracy", "magic_damage_rework", "max_spell", "melee_damage_rework",
        "menu_qol_issue_61", "modern_controls_issue_65", "mug_chance_rework", "mug_drops",
        "music_volume_issue_498", "no_magic_consumption", "party_switch_issue_62",
        "shoot_issue_54", "single_gf", "status_chance_rework", "streamlined_draw",
        "switch_issue_52", "timed_hits", "true_atb_wait_issue_63",
        "vibration_consolidation_issue_66", "world_map_fullscreen_issue_90",
    },
    "ds1": {"ammunition_controls", "ammunition_tweak", "equip_load_percentage", "tweaks"},
}
# Modules named like a tweak that have not moved yet.
ALLOWED_TWEAK_MODULES = {
    "plugins/ff7r/atb_tweaks.py": "#912", "plugins/ff7r/encounter_tweaks.py": "#912",
    "plugins/ff7r/graphics_tweaks.py": "#912", "plugins/ff7r/lockon_tweaks.py": "#912",
    "plugins/ff7r/no_more_cheats_tweaks.py": "#912",
}


def tracked() -> list[str]:
    output = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True,
                            capture_output=True).stdout.decode("utf-8")
    return [path for path in output.split("\0") if path]


class NoTweakPayloadsTests(unittest.TestCase):
    def setUp(self):
        self.files = tracked()

    def test_no_built_tweak_payloads(self):
        found = [path for path in self.files
                 if path.casefold().endswith(TWEAK_SUFFIXES)]
        self.assertEqual(found, [], "Built tweaks belong in a library mod, not in Lexeditor")

    def test_no_tweak_source_folders(self):
        found = sorted({
            "/".join(parts[:index + 1])
            for parts in (path.split("/") for path in self.files)
            for index, part in enumerate(parts[:-1])
            if part in TWEAK_FOLDERS
        } - set(ALLOWED_FOLDERS))
        self.assertEqual(found, [], "Tweak source belongs in the mod that ships it")

    def test_no_unlisted_game_binaries(self):
        found = [path for path in self.files
                 if path.startswith("plugins/")
                 and path.casefold().endswith((".dll", ".asi", ".p"))
                 and not path.startswith(TOOL_PREFIXES)
                 and path not in ALLOWED_BINARIES]
        self.assertEqual(found, [], "A game-loaded binary is a tweak unless listed here with its reason")

    def test_moved_tweak_modules_stay_moved(self):
        found = [path for path in self.files
                 for plugin, modules in MOVED_TWEAK_MODULES.items()
                 if path.startswith(f"plugins/{plugin}/") and path.endswith(".py")
                 and Path(path).stem.removesuffix("_test") in modules]
        self.assertEqual(found, [], "This tweak lives in its tweak mod now")

    def test_no_new_tweak_named_modules(self):
        found = [path for path in self.files
                 if path.startswith("plugins/") and path.endswith("_tweaks.py")
                 and path not in ALLOWED_TWEAK_MODULES]
        self.assertEqual(found, [], "A tweak belongs in a tweak mod")

    def test_allowances_still_exist(self):
        present = set(self.files)
        stale = [path for path in ALLOWED_BINARIES if path not in present]
        stale += [path for path in ALLOWED_TWEAK_MODULES if path not in present]
        stale += [folder for folder in ALLOWED_FOLDERS
                  if not any(path.startswith(folder + "/") for path in present)]
        self.assertEqual(stale, [], "Remove allowances for payloads that already left")


if __name__ == "__main__":
    unittest.main()
