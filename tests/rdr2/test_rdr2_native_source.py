"""Source-only integrity checks for the centralized RDR2 GameplayTweaks runtime."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "plugins" / "rdr2" / "native_runtime" / "GameplayTweaks"


class Rdr2NativeSourceTests(unittest.TestCase):
    def test_source_tree_is_public_source_only(self):
        self.assertTrue((SOURCE / "script.cpp").is_file())
        self.assertTrue((SOURCE / "main.cpp").is_file())
        allowed = {".cpp", ".c", ".h", ".hpp", ".md", ".txt", ".bat"}
        forbidden_parts = {"_downloads", ".build", "build", "outputs", "game-data"}
        forbidden_suffixes = {".asi", ".dll", ".exe", ".rpf", ".ymt", ".ytd", ".zip", ".png", ".dds"}
        for path in SOURCE.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(SOURCE)
            self.assertFalse(forbidden_parts.intersection(relative.parts), relative)
            self.assertNotIn(path.suffix.lower(), forbidden_suffixes, relative)
            self.assertIn(path.suffix.lower(), allowed, relative)

    def test_every_compiled_topic_include_exists(self):
        script = (SOURCE / "script.cpp").read_text("utf-8")
        includes = re.findall(r'#include\s+"(modules/[^"]+\.cpp)"', script)
        self.assertGreaterEqual(len(includes), 40)
        self.assertEqual(len(includes), len(set(includes)))
        for relative in includes:
            self.assertTrue((SOURCE / relative).is_file(), relative)

    def test_distribution_module_inventory_was_not_silently_trimmed(self):
        expected = {
            "always_holster.cpp", "ancient_tomahawk.cpp", "animal_density.cpp",
            "belt_lantern.cpp", "binocular_optics.cpp", "bloodstain_hat.cpp",
            "campfire_icons.cpp", "campfire_policy.cpp", "child_vulnerability.cpp",
            "collectibles_map.cpp", "combat_inventory.cpp", "compendium_glint_probe.cpp",
            "core_cost_guard.cpp", "custom_crafting.cpp", "dual_wield_guard.cpp",
            "duplicate_cigarette_cards.cpp", "fortification_hud.cpp", "gameplay_camera.cpp",
            "honor_actions.cpp", "horse_camera.cpp", "horse_core_clock.cpp",
            "horse_needs.cpp", "horse_persistence.cpp", "human_movement.cpp",
            "hunter_hatchet.cpp", "items_casings.cpp", "movement.cpp", "newspaper_map.cpp",
            "overflow_storage.cpp", "pocketwatch_time.cpp", "premium_cigarette_cards.cpp",
            "projectile_visibility.cpp", "radial_ammo_counts.cpp", "recon.cpp",
            "reusable_canteen.cpp", "serious_crime_payoff.cpp", "settings_menu.cpp",
            "shop_startup_safety.cpp", "shop_state_probe.cpp", "stealth_indicators.cpp",
            "thermometer.cpp", "tonic_refill.cpp", "toxic_presentation.cpp",
            "unified_log.cpp", "wagon_stamina.cpp", "wanted_system.cpp",
            "water_pumps.cpp", "world_collectible_masks.cpp", "world_economy.cpp",
        }
        actual = {path.name for path in (SOURCE / "modules").glob("*.cpp")}
        self.assertEqual(actual, expected)

    def test_build_requires_external_sdk_and_never_installs(self):
        build = (SOURCE / "build.bat").read_text("utf-8")
        self.assertIn("RDR2_SDK_ROOT", build)
        self.assertIn("ScriptHookRDR2.lib", build)
        self.assertIn("/OUT:.build\\GameplayTweaks.asi", build)
        self.assertNotIn("_downloads", build)
        self.assertNotIn("release_manifest", build)
        self.assertNotRegex(build.lower(), r"copy\s+.*red dead redemption|move\s+.*red dead redemption")

    def test_third_party_license_and_known_160_gap_are_explicit(self):
        license_text = (ROOT / "plugins" / "rdr2" / "credits.md").read_text("utf-8")
        self.assertIn("MinHook", license_text)
        readme = (SOURCE / "README.md").read_text("utf-8")
        self.assertIn("ccc6c4adcb9262dbd62aeea7901d5864f64680fc", readme)
        self.assertIn("player_core_rates.cpp", readme)
        self.assertFalse((SOURCE / "modules" / "player_core_rates.cpp").exists())


if __name__ == "__main__":
    unittest.main()
