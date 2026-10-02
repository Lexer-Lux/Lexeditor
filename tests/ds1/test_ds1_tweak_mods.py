"""DS1 tweak mods: saved in the library, built together, applied safely.

Uses the synthetic executable from test_ds1_exe_patches, so no game files are
needed: its fingerprint stands in for the real build's during each test.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_ds1_exe_patches import VANILLA, HOOK_A, HOOK_B, island  # noqa: E402
from core import script_mods  # noqa: E402
from plugins.ds1 import exe_patches, tweak_mods  # noqa: E402

# The guard every test below replaces, kept for the one that checks it.
REAL_GUARD = tweak_mods.ensure_game_closed
TWEAK = '''import json

def build(settings, context):
    return {"native/%s.json": json.dumps(%s)}
'''
SPECS = {
    "alpha": {"version": 1, "islands": [island("payload", rva=0x6000)],
              "hooks": [{"rva": HOOK_A, "original": "E800000000",
                         "branch": {"opcode": "E8", "island": "payload", "offset": 4}}]},
    "beta": {"version": 1, "islands": [island("display")],
             "hooks": [{"rva": HOOK_B, "original": "488D1500000000",
                        "branch": {"opcode": "E9", "island": "display", "offset": 4}, "pad": "9090"}]},
}


class LoaderTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="lexeditor-ds1-tweaks-")
        self.addCleanup(temp.cleanup)
        self.temp = Path(temp.name)
        self.library = self.temp / "library"
        self.game = self.temp / "game"
        self.game.mkdir()
        self.live = self.game / exe_patches.EXECUTABLE
        self.live.write_bytes(VANILLA)
        for order, mod_id in enumerate(SPECS):
            root = self.library / mod_id.title()
            (root / "script").mkdir(parents=True)
            (root / "script" / "__init__.py").write_text("", encoding="utf-8")
            (root / "script" / "tweak.py").write_text(TWEAK % (mod_id, repr(SPECS[mod_id])), encoding="utf-8")
            (root / "settings.schema.json").write_text(json.dumps({"title": mod_id.upper()}), encoding="utf-8")
            (root / "mod.json").write_text(json.dumps({"id": mod_id, "name": mod_id.title(), "order": order,
                                                       "enabled": False, "script": {"version": 1}}), encoding="utf-8")
        for patcher in (
            mock.patch.dict(os.environ, {script_mods.TRUST_ENV: str(self.temp / "trust.json")}),
            mock.patch.object(exe_patches, "VANILLA_SIZE", len(VANILLA)),
            mock.patch.object(exe_patches, "VANILLA_SHA256", hashlib.sha256(VANILLA).hexdigest()),
            mock.patch.object(tweak_mods, "ensure_game_closed"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        for row in tweak_mods.tweak_rows(self.library):
            script_mods.set_trusted(Path(row["path"]), True)

    def enable(self, **switches):
        tweak_mods.save({mod_id: {"enabled": on} for mod_id, on in switches.items()}, self.library)

    def expected(self, *ids):
        return exe_patches.compose(VANILLA, [exe_patches.validate(SPECS[i], i.title()) for i in ids])

    def files(self):
        return sorted(path.name for path in self.game.iterdir())

    def test_switches_save_together_or_not_at_all(self):
        self.enable(alpha=True)
        self.assertEqual([(r["id"], r["enabled"]) for r in tweak_mods.tweak_rows(self.library)],
                         [("alpha", True), ("beta", False)])
        for bad in ({"alpha": {"enabled": False}, "missing": {"enabled": True}},
                    {"alpha": {"enabled": False}, "beta": {"enabled": "yes"}},
                    {"alpha": {"other": 1}}):
            with self.assertRaises(tweak_mods.TweakError):
                tweak_mods.save(bad, self.library)
        self.assertTrue(tweak_mods.tweak_rows(self.library)[0]["enabled"])

    def test_off_tweaks_change_nothing(self):
        result = tweak_mods.apply(self.game, self.library)
        self.assertEqual(self.live.read_bytes(), VANILLA)
        self.assertEqual(self.files(), [exe_patches.EXECUTABLE])
        self.assertEqual((result["state"], result["applied"]), ("vanilla", []))

    def test_untrusted_tweak_never_builds(self):
        self.enable(alpha=True)
        script_mods.set_trusted(Path(tweak_mods.tweak_rows(self.library)[0]["path"]), False)
        with self.assertRaisesRegex(tweak_mods.TweakError, "trust"):
            tweak_mods.apply(self.game, self.library)
        self.assertEqual(self.live.read_bytes(), VANILLA)

    def test_apply_combines_from_the_original_and_restore_puts_it_back(self):
        self.enable(alpha=True)
        tweak_mods.apply(self.game, self.library)
        self.assertEqual(self.live.read_bytes(), self.expected("alpha"))
        self.assertEqual(self.files(), sorted([exe_patches.EXECUTABLE, tweak_mods.BACKUP_FILE, tweak_mods.MANIFEST_FILE]))
        self.enable(beta=True)
        result = tweak_mods.apply(self.game, self.library)
        # Both together, built from the original, never stacked on the last output.
        self.assertEqual(self.live.read_bytes(), self.expected("alpha", "beta"))
        self.assertEqual((result["state"], result["applied"]), ("tweaked", ["Alpha", "Beta"]))
        self.assertEqual((self.game / tweak_mods.BACKUP_FILE).read_bytes(), VANILLA)
        result = tweak_mods.restore(self.game, self.library)
        self.assertEqual(self.live.read_bytes(), VANILLA)
        self.assertEqual(result["state"], "vanilla")
        self.assertNotIn(tweak_mods.MANIFEST_FILE, self.files())
        self.assertTrue(all(row["enabled"] for row in tweak_mods.tweak_rows(self.library)), "restore keeps the switches")

    def test_turning_every_tweak_off_and_applying_restores(self):
        self.enable(alpha=True)
        tweak_mods.apply(self.game, self.library)
        self.enable(alpha=False)
        tweak_mods.apply(self.game, self.library)
        self.assertEqual(self.live.read_bytes(), VANILLA)

    def test_an_executable_changed_elsewhere_is_never_overwritten(self):
        self.enable(alpha=True)
        tweak_mods.apply(self.game, self.library)
        foreign = self.live.read_bytes()[:-1] + b"\x7f"
        self.live.write_bytes(foreign)
        for action in (tweak_mods.apply, tweak_mods.restore):
            with self.assertRaisesRegex(tweak_mods.TweakError, "outside Lexeditor"):
                action(self.game, self.library)
        self.assertEqual(self.live.read_bytes(), foreign)
        self.assertIn("outside Lexeditor", tweak_mods.status(self.game, self.library)["problem"])

    def test_a_changed_or_missing_original_is_refused(self):
        self.enable(alpha=True)
        tweak_mods.apply(self.game, self.library)
        patched = self.live.read_bytes()
        (self.game / tweak_mods.BACKUP_FILE).write_bytes(VANILLA[:-1] + b"\x01")
        with self.assertRaisesRegex(tweak_mods.TweakError, "original"):
            tweak_mods.restore(self.game, self.library)
        (self.game / tweak_mods.BACKUP_FILE).unlink()
        with self.assertRaisesRegex(tweak_mods.TweakError, "original"):
            tweak_mods.restore(self.game, self.library)
        self.assertEqual(self.live.read_bytes(), patched)

    def test_a_failed_write_keeps_the_original(self):
        self.enable(alpha=True)
        with mock.patch.object(tweak_mods, "atomic_write", side_effect=OSError("locked")):
            with self.assertRaises(OSError):
                tweak_mods.apply(self.game, self.library)
        self.assertEqual(self.live.read_bytes(), VANILLA)
        self.assertEqual((self.game / tweak_mods.BACKUP_FILE).read_bytes(), VANILLA)

    def test_a_change_while_preparing_is_refused(self):
        self.enable(alpha=True)
        real = exe_patches.compose

        def compose_then_tamper(*args):
            result = real(*args)
            self.live.write_bytes(VANILLA[:-1] + b"\x02")
            return result
        with mock.patch.object(exe_patches, "compose", compose_then_tamper):
            with self.assertRaisesRegex(tweak_mods.TweakError, "changed while"):
                tweak_mods.apply(self.game, self.library)
        self.assertEqual(self.live.read_bytes(), VANILLA[:-1] + b"\x02")

    def test_a_running_game_stops_everything_before_any_write(self):
        self.enable(alpha=True)
        with mock.patch.object(tweak_mods, "ensure_game_closed", side_effect=tweak_mods.TweakError("Close Dark Souls")):
            with self.assertRaisesRegex(tweak_mods.TweakError, "Close"):
                tweak_mods.apply(self.game, self.library)
        self.assertEqual(self.files(), [exe_patches.EXECUTABLE])

    @unittest.skipUnless(os.name == "nt", "the running-process probe is Windows-only")
    def test_the_real_guard_sees_the_game_process(self):
        with mock.patch.object(tweak_mods, "live_processes", return_value=[exe_patches.EXECUTABLE]):
            with self.assertRaisesRegex(tweak_mods.TweakError, "Close"):
                REAL_GUARD()

    def test_links_are_refused(self):
        linked = self.game / "linked.exe"
        try:
            os.link(self.live, linked)
        except OSError:
            self.skipTest("hard links are not available here")
        with self.assertRaisesRegex(tweak_mods.TweakError, "hard link"):
            tweak_mods.apply(self.game, self.library)
        self.assertEqual(self.live.read_bytes(), VANILLA)


if __name__ == "__main__":
    unittest.main()
