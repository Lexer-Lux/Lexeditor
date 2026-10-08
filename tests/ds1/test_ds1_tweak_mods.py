"""DS1 tweak mods: saved in the library, built together, applied safely.

Apply never writes the executable: it installs Lexeditor's loader and the
combined patch description beside it (plugins/ds1/runtime/). Uses the
synthetic executable from test_ds1_exe_patches, so no game files are needed:
its fingerprint stands in for the real build's during each test.
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
    # The first 64 KB boundary past the synthetic image (see exe_patches).
    "alpha": {"version": 1, "islands": [island("payload", rva=0x10000)],
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
        return exe_patches.runtime_patch(VANILLA, [exe_patches.validate(SPECS[i], i.title()) for i in ids])

    def runtime(self):
        return (self.game / tweak_mods.RUNTIME_PATCH).read_bytes()

    def old_install(self, *ids):
        """What an earlier Lexeditor left: tweaks built into the executable."""
        built = exe_patches.compose(VANILLA, [exe_patches.validate(SPECS[i], i.title()) for i in ids])
        self.live.write_bytes(built)
        (self.game / tweak_mods.BACKUP_FILE).write_bytes(VANILLA)
        (self.game / tweak_mods.MANIFEST_FILE).write_text(json.dumps({
            "version": 2, "sha256": hashlib.sha256(built).hexdigest(), "mods": [i.title() for i in ids],
            "project": None, "pending": None}), encoding="utf-8")
        return built

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

    def test_off_tweaks_preserve_game_and_create_only_bounded_lock(self):
        # Reading the catalogue or saving switches does not install anything.
        tweak_mods.status(self.game, self.library)
        self.enable(alpha=False, beta=False)
        self.assertEqual(self.files(), [exe_patches.EXECUTABLE])
        result = tweak_mods.apply(self.game, self.library)
        self.assertEqual(self.live.read_bytes(), VANILLA)
        # Explicit Apply serializes even a no-op. Its persistent one-byte lock
        # is metadata, not an executable edit, backup or generated tweak.
        self.assertEqual(self.files(), sorted([exe_patches.EXECUTABLE, tweak_mods.LOCK_FILE]))
        self.assertEqual((self.game / tweak_mods.LOCK_FILE).read_bytes(), b"0")
        self.assertEqual((result["state"], result["applied"]), ("vanilla", []))

    def test_untrusted_tweak_never_builds(self):
        self.enable(alpha=True)
        script_mods.set_trusted(Path(tweak_mods.tweak_rows(self.library)[0]["path"]), False)
        with self.assertRaisesRegex(tweak_mods.TweakError, "trust"):
            tweak_mods.apply(self.game, self.library)
        self.assertEqual(self.live.read_bytes(), VANILLA)

    def test_apply_installs_the_loader_and_never_writes_the_executable(self):
        self.enable(alpha=True)
        tweak_mods.apply(self.game, self.library)
        self.assertEqual(self.live.read_bytes(), VANILLA)
        self.assertEqual(self.runtime(), self.expected("alpha"))
        self.assertEqual((self.game / tweak_mods.RUNTIME_DLL).read_bytes(), tweak_mods.loader_bytes())
        self.assertEqual(self.files(), sorted([exe_patches.EXECUTABLE, tweak_mods.LOCK_FILE, tweak_mods.RUNTIME_DLL,
                                               tweak_mods.RUNTIME_PATCH, tweak_mods.RUNTIME_RECORD]))
        lock = self.game / tweak_mods.LOCK_FILE
        lock_identity = (lock.stat().st_dev, lock.stat().st_ino)
        self.assertEqual(lock.read_bytes(), b"0")
        self.enable(beta=True)
        result = tweak_mods.apply(self.game, self.library)
        # Both together, built from the original, never stacked on the last output.
        self.assertEqual(self.runtime(), self.expected("alpha", "beta"))
        self.assertEqual(self.live.read_bytes(), VANILLA)
        self.assertEqual((result["state"], result["applied"]), ("tweaked", ["Alpha", "Beta"]))
        result = tweak_mods.restore(self.game, self.library)
        self.assertEqual(self.live.read_bytes(), VANILLA)
        self.assertEqual(result["state"], "vanilla")
        self.assertEqual(self.files(), sorted([exe_patches.EXECUTABLE, tweak_mods.LOCK_FILE]))
        self.assertEqual(lock.read_bytes(), b"0")
        self.assertEqual((lock.stat().st_dev, lock.stat().st_ino), lock_identity,
                         "Apply and Restore retain the same lock inode")
        self.assertTrue(all(row["enabled"] for row in tweak_mods.tweak_rows(self.library)), "restore keeps the switches")

    def test_turning_every_tweak_off_and_applying_removes_the_loader(self):
        self.enable(alpha=True)
        tweak_mods.apply(self.game, self.library)
        self.enable(alpha=False)
        tweak_mods.apply(self.game, self.library)
        self.assertEqual(self.live.read_bytes(), VANILLA)
        self.assertEqual(self.files(), sorted([exe_patches.EXECUTABLE, tweak_mods.LOCK_FILE]))

    def test_an_executable_an_earlier_lexeditor_patched_is_put_back_once(self):
        self.old_install("alpha")
        self.enable(alpha=True)
        before = tweak_mods.status(self.game, self.library)
        self.assertTrue(before["builtIntoExecutable"])
        result = tweak_mods.apply(self.game, self.library)
        self.assertEqual(self.live.read_bytes(), VANILLA)
        self.assertEqual(self.runtime(), self.expected("alpha"))
        self.assertEqual((result["applied"], result["builtIntoExecutable"]), (["Alpha"], False))
        self.assertNotIn(tweak_mods.MANIFEST_FILE, self.files())

    def test_another_mods_dinput8_is_never_replaced(self):
        (self.game / tweak_mods.RUNTIME_DLL).write_bytes(b"someone else's loader")
        self.enable(alpha=True)
        with self.assertRaisesRegex(tweak_mods.TweakError, "Another mod's dinput8.dll"):
            tweak_mods.apply(self.game, self.library)
        self.assertEqual((self.game / tweak_mods.RUNTIME_DLL).read_bytes(), b"someone else's loader")
        tweak_mods.restore(self.game, self.library)
        self.assertEqual((self.game / tweak_mods.RUNTIME_DLL).read_bytes(), b"someone else's loader")

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
        patched = self.old_install("alpha")
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
        self.assertNotIn(tweak_mods.RUNTIME_DLL, self.files())

    def test_a_change_while_preparing_is_refused(self):
        self.enable(alpha=True)
        real = exe_patches.runtime_patch

        def build_then_tamper(*args):
            result = real(*args)
            self.live.write_bytes(VANILLA[:-1] + b"\x02")
            return result
        with mock.patch.object(exe_patches, "runtime_patch", build_then_tamper):
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


LAYOUT_TWEAK = '''import json

def build(settings, context):
    return {"native/%s.json": json.dumps(%s), "layout/%s.json": json.dumps(%s)}
'''


class LayoutLoaderTests(unittest.TestCase):
    """A tweak that adds menu rows: the layout follows the executable's rules."""

    def setUp(self):
        from test_ds1_menu_layout import STAMINA, dcx, drb
        from plugins.ds1 import menu_layout
        self.menu_layout = menu_layout
        temp = tempfile.TemporaryDirectory(prefix="lexeditor-ds1-layout-")
        self.addCleanup(temp.cleanup)
        self.temp = Path(temp.name)
        self.library = self.temp / "library"
        self.game = self.temp / "game"
        (self.game / "menu").mkdir(parents=True)
        self.live = self.game / exe_patches.EXECUTABLE
        self.live.write_bytes(VANILLA)
        self.layout = self.game / "menu" / "menu.drb.dcx"
        self.vanilla_layout = dcx(drb())
        self.layout.write_bytes(self.vanilla_layout)
        self.nodes = {"version": 1, "nodes": STAMINA}
        root = self.library / "Details"
        (root / "script").mkdir(parents=True)
        (root / "script" / "__init__.py").write_text("", encoding="utf-8")
        (root / "script" / "tweak.py").write_text(
            LAYOUT_TWEAK % ("details", repr(SPECS["alpha"]), "details", repr(self.nodes)), encoding="utf-8")
        (root / "mod.json").write_text(json.dumps({"id": "details", "name": "Details", "enabled": False,
                                                   "script": {"version": 1}}), encoding="utf-8")
        for patcher in (
            mock.patch.dict(os.environ, {script_mods.TRUST_ENV: str(self.temp / "trust.json")}),
            mock.patch.object(exe_patches, "VANILLA_SIZE", len(VANILLA)),
            mock.patch.object(exe_patches, "VANILLA_SHA256", hashlib.sha256(VANILLA).hexdigest()),
            mock.patch.object(menu_layout, "VANILLA_SIZE", len(self.vanilla_layout)),
            mock.patch.object(menu_layout, "VANILLA_SHA256", hashlib.sha256(self.vanilla_layout).hexdigest()),
            mock.patch.object(tweak_mods, "ensure_game_closed"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        script_mods.set_trusted(root, True)

    def enable(self, on=True):
        tweak_mods.save({"details": {"enabled": on}}, self.library)

    def expected_layout(self):
        spec = self.menu_layout.validate(self.nodes, "Details")
        return self.menu_layout.compose(self.vanilla_layout, [spec])

    def menu_files(self):
        return sorted(path.name for path in (self.game / "menu").iterdir())

    def test_a_game_without_layout_tweaks_never_touches_the_layout(self):
        tweak_mods.apply(self.game, self.library)
        self.assertEqual(self.menu_files(), ["menu.drb.dcx"])
        self.assertEqual(self.layout.read_bytes(), self.vanilla_layout)

    def test_apply_changes_both_files_and_restore_puts_both_back(self):
        self.enable()
        result = tweak_mods.apply(self.game, self.library)
        self.assertEqual(self.layout.read_bytes(), self.expected_layout())
        self.assertEqual(self.live.read_bytes(), VANILLA)
        self.assertTrue((self.game / tweak_mods.RUNTIME_PATCH).is_file())
        self.assertEqual(self.menu_files(), ["menu.drb.dcx", "menu.drb.dcx.lexeditor-original",
                                             "menu.drb.dcx.lexeditor-tweaks.json"])
        self.assertEqual((result["state"], result["applied"], result["problem"]), ("tweaked", ["Details"], ""))
        result = tweak_mods.restore(self.game, self.library)
        self.assertEqual(self.layout.read_bytes(), self.vanilla_layout)
        self.assertEqual(self.live.read_bytes(), VANILLA)
        self.assertEqual((result["state"], result["applied"]), ("vanilla", []))
        self.assertNotIn("menu.drb.dcx.lexeditor-tweaks.json", self.menu_files())

    def test_turning_the_tweak_off_and_applying_restores_the_layout(self):
        self.enable()
        tweak_mods.apply(self.game, self.library)
        self.enable(False)
        result = tweak_mods.apply(self.game, self.library)
        self.assertEqual(self.layout.read_bytes(), self.vanilla_layout)
        self.assertEqual(result["state"], "vanilla")

    def test_a_layout_changed_elsewhere_is_never_overwritten(self):
        self.enable()
        tweak_mods.apply(self.game, self.library)
        foreign = self.layout.read_bytes() + b"\0"
        self.layout.write_bytes(foreign)
        for action in (tweak_mods.apply, tweak_mods.restore):
            with self.assertRaisesRegex(tweak_mods.TweakError, "menu layout was changed outside Lexeditor"):
                action(self.game, self.library)
        self.assertEqual(self.layout.read_bytes(), foreign)
        self.assertIn("menu layout", tweak_mods.status(self.game, self.library)["problem"])

    def test_a_layout_the_tweak_cannot_patch_changes_nothing(self):
        self.nodes["nodes"] = [{**self.nodes["nodes"][0], "lookLike": "missing"}]
        root = self.library / "Details"
        (root / "script" / "tweak.py").write_text(
            LAYOUT_TWEAK % ("details", repr(SPECS["alpha"]), "details", repr(self.nodes)), encoding="utf-8")
        script_mods.set_trusted(root, True)
        self.enable()
        with self.assertRaisesRegex(tweak_mods.TweakError, "missing"):
            tweak_mods.apply(self.game, self.library)
        self.assertEqual(self.live.read_bytes(), VANILLA)
        self.assertEqual(self.menu_files(), ["menu.drb.dcx"])

    def test_a_failed_layout_write_installs_no_loader(self):
        self.enable()
        real = tweak_mods._write

        def fail_layout(game_root, before, after, mods, managed=tweak_mods.EXECUTABLE, **options):
            if managed is tweak_mods.LAYOUT:
                raise OSError("locked")
            return real(game_root, before, after, mods, managed, **options)
        with mock.patch.object(tweak_mods, "_write", fail_layout):
            with self.assertRaises(OSError):
                tweak_mods.apply(self.game, self.library)
        self.assertEqual(self.live.read_bytes(), VANILLA)
        self.assertEqual(self.layout.read_bytes(), self.vanilla_layout)
        self.assertFalse((self.game / tweak_mods.RUNTIME_DLL).exists())


if __name__ == "__main__":
    unittest.main()
