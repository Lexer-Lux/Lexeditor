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


def enable_loader(library, on=True):
    """Switch the loader mod on or off, creating it on first use."""
    folder = tweak_mods.ensure_loader_mod(Path(library))
    data = json.loads((folder / "mod.json").read_text(encoding="utf-8"))
    (folder / "mod.json").write_text(json.dumps({**data, "enabled": on}), encoding="utf-8")


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
            mock.patch.object(exe_patches, "VANILLA_SIZE", len(VANILLA)),
            mock.patch.object(exe_patches, "VANILLA_SHA256", hashlib.sha256(VANILLA).hexdigest()),
            mock.patch.object(tweak_mods, "ensure_game_closed"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        enable_loader(self.library)

    def enable(self, **switches):
        tweak_mods.save({mod_id: {"enabled": on} for mod_id, on in switches.items()}, self.library)

    def expected(self, *ids):
        from plugins.ds1 import runtime_mods
        return {name: runtime_mods.build(VANILLA, [exe_patches.validate(SPECS[name], name.title())]) for name in ids} or b''

    def runtime(self):
        # Ordinary mods now live in independently loadable library folders.
        # The loader-owned patch must not duplicate any of their hooks.
        self.assertEqual((self.game / tweak_mods.RUNTIME_PATCH).read_bytes(), b'')
        return {name: (self.library/name.title()/'runtime.lxd').read_bytes() for name in SPECS
                if json.loads((self.library/name.title()/'mod.json').read_text())['enabled']} or b''

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

    def test_a_switch_that_breaks_a_requirement_saves_nothing(self):
        alpha = self.library / "Alpha" / "mod.json"
        data = json.loads(alpha.read_text(encoding="utf-8"))
        alpha.write_text(json.dumps({**data, "requires": ["beta"]}), encoding="utf-8")
        with self.assertRaisesRegex(tweak_mods.TweakError, "Alpha requires beta, which is switched off"):
            self.enable(alpha=True)
        self.assertFalse(tweak_mods.tweak_rows(self.library)[0]["enabled"])
        self.enable(alpha=True, beta=True)
        with self.assertRaisesRegex(tweak_mods.TweakError, "Alpha requires Beta"):
            self.enable(beta=False)
        self.assertTrue(tweak_mods.tweak_rows(self.library)[1]["enabled"])

    def test_off_tweaks_preserve_game_and_create_only_bounded_lock(self):
        # Reading the catalogue or saving switches does not install anything.
        tweak_mods.status(self.game, self.library)
        self.enable(alpha=False, beta=False)
        enable_loader(self.library, False)
        self.assertEqual(self.files(), [exe_patches.EXECUTABLE])
        result = tweak_mods.apply(self.game, self.library)
        self.assertEqual(self.live.read_bytes(), VANILLA)
        # Explicit Apply serializes even a no-op. Its persistent one-byte lock
        # is metadata, not an executable edit, backup or generated tweak.
        self.assertEqual(self.files(), sorted([exe_patches.EXECUTABLE, tweak_mods.LOCK_FILE]))
        self.assertEqual((self.game / tweak_mods.LOCK_FILE).read_bytes(), b"0")
        self.assertEqual((result["state"], result["applied"]), ("vanilla", []))

    def test_the_loader_mod_installs_the_loader_even_with_no_tweak(self):
        # The loader is an ordinary library mod (mod.json only): switching it
        # on installs the protected loader (Arxan off, no network) even with
        # no tweak enabled.
        self.assertEqual(tweak_mods.loader_mod_state(self.library), (True, True))
        result = tweak_mods.apply(self.game, self.library)
        self.assertEqual((self.game / tweak_mods.RUNTIME_DLL).read_bytes(), tweak_mods.loader_bytes(online=True))
        self.assertEqual(self.runtime(), b"")
        self.assertEqual(result["applied"], [])
        self.assertEqual(self.live.read_bytes(), VANILLA)
        # Tweaks ride along.
        self.enable(alpha=True)
        tweak_mods.apply(self.game, self.library)
        self.assertEqual(self.runtime(), self.expected("alpha"))
        # Off, with the last tweak: the loader goes away too.
        self.enable(alpha=False)
        enable_loader(self.library, False)
        result = tweak_mods.apply(self.game, self.library)
        self.assertEqual(self.files(), sorted([exe_patches.EXECUTABLE, tweak_mods.LOCK_FILE]))
        self.assertEqual(result["state"], "vanilla")

    def test_a_removed_debug_flag_migrates_to_an_enabled_loader_mod(self):
        fresh = self.temp / "fresh-library"
        fresh.mkdir()
        (fresh / tweak_mods.DEBUG_FILE).write_text(json.dumps({"debugMode": True}), encoding="utf-8")
        folder = tweak_mods.ensure_loader_mod(fresh)
        stored = json.loads((folder / "mod.json").read_text(encoding="utf-8"))
        self.assertEqual((stored["id"], stored["enabled"], stored["order"]), ("lexeditor-loader", True, 0))
        self.assertNotIn("script", stored)
        self.assertFalse((fresh / tweak_mods.DEBUG_FILE).exists())

    def test_build_specs_refuses_executable_patches_while_the_loader_is_off(self):
        self.enable(alpha=True, beta=True)
        enable_loader(self.library, False)
        with self.assertRaisesRegex(tweak_mods.TweakError,
                                    "Alpha and Beta require Lexeditor Loader, which is switched off"):
            tweak_mods.build_specs(self.library)
        stored = json.loads((self.library / "Alpha" / "mod.json").read_text(encoding="utf-8"))
        self.assertNotIn("requires", stored)
        enable_loader(self.library)
        self.assertEqual(len(tweak_mods.build_specs(self.library)), 2)

    def test_prepare_refuses_project_native_rules_while_the_loader_is_off(self):
        enable_loader(self.library, False)
        project = {"path": "mods/Native", "settingsHash": "ab" * 32, "spec": SPECS["alpha"]}
        with self.assertRaisesRegex(tweak_mods.TweakError,
                                    "Project native rules requires Lexeditor Loader, which is switched off"):
            tweak_mods.prepare(self.game, self.library, project=project)
        enable_loader(self.library)
        plan = tweak_mods.prepare(self.game, self.library, project=project)
        self.assertIsNotNone(plan["runtime"]["patch"])

    def test_enabled_tweak_builds_with_no_trust_step(self):
        self.enable(alpha=True)
        tweak_mods.apply(self.game, self.library)
        self.assertEqual(self.runtime(), self.expected("alpha"))

    def test_apply_installs_the_loader_and_never_writes_the_executable(self):
        self.enable(alpha=True)
        tweak_mods.apply(self.game, self.library)
        self.assertEqual(self.live.read_bytes(), VANILLA)
        self.assertEqual(self.runtime(), self.expected("alpha"))
        self.assertEqual((self.game / tweak_mods.RUNTIME_DLL).read_bytes(), tweak_mods.loader_bytes(online=True))
        self.assertEqual(self.files(), sorted([exe_patches.EXECUTABLE, tweak_mods.LOCK_FILE, tweak_mods.RUNTIME_DLL,
                                               tweak_mods.RUNTIME_PATCH, tweak_mods.RUNTIME_RECORD, tweak_mods.RUNTIME_CONFIG]))
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

    def test_turning_everything_off_and_applying_removes_the_loader(self):
        self.enable(alpha=True)
        tweak_mods.apply(self.game, self.library)
        self.enable(alpha=False)
        enable_loader(self.library, False)
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
            mock.patch.object(exe_patches, "VANILLA_SIZE", len(VANILLA)),
            mock.patch.object(exe_patches, "VANILLA_SHA256", hashlib.sha256(VANILLA).hexdigest()),
            mock.patch.object(menu_layout, "VANILLA_SIZE", len(self.vanilla_layout)),
            mock.patch.object(menu_layout, "VANILLA_SHA256", hashlib.sha256(self.vanilla_layout).hexdigest()),
            mock.patch.object(tweak_mods, "ensure_game_closed"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        enable_loader(self.library)

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


ESD_TWEAK = '''import json

def build(settings, context):
    return {"native/%s.json": json.dumps(%s), "esd/%s.json": json.dumps(%s)}
'''


class EsdLoaderTests(unittest.TestCase):
    """A tweak that adds menu commands: the scripts follow the layout's rules."""

    def setUp(self):
        from test_ds1_menu_scripts import ANCHOR, NEW, archive, build_script
        from plugins.ds1 import menu_scripts
        self.menu_scripts = menu_scripts
        temp = tempfile.TemporaryDirectory(prefix="lexeditor-ds1-esd-")
        self.addCleanup(temp.cleanup)
        self.temp = Path(temp.name)
        self.library = self.temp / "library"
        self.game = self.temp / "game"
        (self.game / "menu").mkdir(parents=True)
        self.live = self.game / exe_patches.EXECUTABLE
        self.live.write_bytes(VANILLA)
        self.vanilla = {"ingame": archive({"i02-00.esd": build_script().to_bytes()}),
                        "common": archive({"e00-00.esd": build_script(where="sub").to_bytes()})}
        self.live_ingame = self.game / "menu" / "ingame.menuesdbnd.dcx"
        self.live_common = self.game / "menu" / "common.menuesdbnd.dcx"
        self.live_ingame.write_bytes(self.vanilla["ingame"])
        self.live_common.write_bytes(self.vanilla["common"])
        self.spec = {"version": 1, "changes": [
            {"archive": "ingame", "script": "i02-00.esd",
             "after": dict(ANCHOR), "commands": [dict(NEW)]},
            {"archive": "common", "script": "e00-00.esd",
             "after": {"bank": 1, "id": 7, "args": []},
             "commands": [{"bank": 1, "id": 8, "args": []}]}]}
        root = self.library / "Scripts"
        (root / "script").mkdir(parents=True)
        (root / "script" / "__init__.py").write_text("", encoding="utf-8")
        (root / "script" / "tweak.py").write_text(
            ESD_TWEAK % ("scripts", repr(SPECS["alpha"]), "scripts", repr(self.spec)), encoding="utf-8")
        (root / "mod.json").write_text(json.dumps({"id": "scripts", "name": "Scripts", "enabled": False,
                                                   "script": {"version": 1}}), encoding="utf-8")
        for patcher in (
            mock.patch.object(exe_patches, "VANILLA_SIZE", len(VANILLA)),
            mock.patch.object(exe_patches, "VANILLA_SHA256", hashlib.sha256(VANILLA).hexdigest()),
            mock.patch.object(menu_scripts, "VANILLA",
                              {name: (len(data), hashlib.sha256(data).hexdigest())
                               for name, data in self.vanilla.items()}),
            mock.patch.object(tweak_mods, "ensure_game_closed"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        enable_loader(self.library)

    def enable(self, on=True):
        tweak_mods.save({"scripts": {"enabled": on}}, self.library)

    def expected(self, name):
        specs = [self.menu_scripts.validate(self.spec, "Scripts")]
        return self.menu_scripts.compose(self.vanilla[name], specs, name)

    def menu_files(self):
        return sorted(path.name for path in (self.game / "menu").iterdir())

    def test_a_game_without_script_tweaks_never_touches_the_archives(self):
        tweak_mods.apply(self.game, self.library)
        self.assertEqual(self.menu_files(), ["common.menuesdbnd.dcx", "ingame.menuesdbnd.dcx"])
        self.assertEqual(self.live_ingame.read_bytes(), self.vanilla["ingame"])
        self.assertEqual(self.live_common.read_bytes(), self.vanilla["common"])

    def test_apply_changes_both_archives_and_restore_puts_both_back(self):
        self.enable()
        result = tweak_mods.apply(self.game, self.library)
        self.assertEqual(self.live_ingame.read_bytes(), self.expected("ingame"))
        self.assertEqual(self.live_common.read_bytes(), self.expected("common"))
        self.assertEqual(self.live.read_bytes(), VANILLA)
        self.assertTrue((self.game / tweak_mods.RUNTIME_PATCH).is_file())
        self.assertEqual(self.menu_files(), ["common.menuesdbnd.dcx",
                                             "common.menuesdbnd.dcx.lexeditor-original",
                                             "common.menuesdbnd.dcx.lexeditor-tweaks.json",
                                             "ingame.menuesdbnd.dcx",
                                             "ingame.menuesdbnd.dcx.lexeditor-original",
                                             "ingame.menuesdbnd.dcx.lexeditor-tweaks.json"])
        self.assertEqual((result["state"], result["applied"], result["problem"]),
                         ("tweaked", ["Scripts"], ""))
        result = tweak_mods.restore(self.game, self.library)
        self.assertEqual(self.live_ingame.read_bytes(), self.vanilla["ingame"])
        self.assertEqual(self.live_common.read_bytes(), self.vanilla["common"])
        self.assertEqual((result["state"], result["applied"]), ("vanilla", []))
        self.assertEqual(self.menu_files(), ["common.menuesdbnd.dcx",
                                             "common.menuesdbnd.dcx.lexeditor-original",
                                             "ingame.menuesdbnd.dcx",
                                             "ingame.menuesdbnd.dcx.lexeditor-original"])

    def test_turning_the_tweak_off_and_applying_restores_the_archives(self):
        self.enable()
        tweak_mods.apply(self.game, self.library)
        self.enable(False)
        result = tweak_mods.apply(self.game, self.library)
        self.assertEqual(self.live_ingame.read_bytes(), self.vanilla["ingame"])
        self.assertEqual(self.live_common.read_bytes(), self.vanilla["common"])
        self.assertEqual(result["state"], "vanilla")

    def test_scripts_changed_elsewhere_are_never_overwritten(self):
        self.enable()
        tweak_mods.apply(self.game, self.library)
        foreign = self.live_ingame.read_bytes() + b"\0"
        self.live_ingame.write_bytes(foreign)
        for action in (tweak_mods.apply, tweak_mods.restore):
            with self.assertRaisesRegex(tweak_mods.TweakError,
                                        "ingame menu scripts was changed outside Lexeditor"):
                action(self.game, self.library)
        self.assertEqual(self.live_ingame.read_bytes(), foreign)
        self.assertIn("ingame menu scripts", tweak_mods.status(self.game, self.library)["problem"])

    def test_scripts_the_tweak_cannot_patch_change_nothing(self):
        bad = {"version": 1, "changes": [
            {"archive": "ingame", "script": "i02-00.esd",
             "after": {"bank": 1, "id": 999, "args": []}, "commands": [{"bank": 1, "id": 29, "args": ['"Ins_I02-02"', '"button5_0"', '"button_item_select"', '"Ins_button5_item_select"', '"FrpgMenuDlgEquipListIcon"']}]}]}
        root = self.library / "Scripts"
        (root / "script" / "tweak.py").write_text(
            ESD_TWEAK % ("scripts", repr(SPECS["alpha"]), "scripts", repr(bad)), encoding="utf-8")
        self.enable()
        with self.assertRaisesRegex(tweak_mods.TweakError, "no command matching"):
            tweak_mods.apply(self.game, self.library)
        self.assertEqual(self.live.read_bytes(), VANILLA)
        self.assertEqual(self.menu_files(), ["common.menuesdbnd.dcx", "ingame.menuesdbnd.dcx"])


if __name__ == "__main__":
    unittest.main()


class BuildContextTests(unittest.TestCase):
    def test_game_params_is_none_outside_an_apply(self):
        self.assertIsNone(tweak_mods.BuildContext({}).game_params())

    def test_game_params_combines_active_mods_over_vanilla_once(self):
        with tempfile.TemporaryDirectory() as folder:
            game = Path(folder)
            source = game / "param.dcx"
            source.write_bytes(b"vanilla")
            from plugins.ds1.mod_loader import RELATIVE as relative
            mod = mock.Mock(files={relative: b"mod"})
            mod.name = "A mod"
            with mock.patch("plugins.ds1.deployment.vanilla_source", return_value=source), \
                 mock.patch("plugins.ds1.mod_loader.active_mods", return_value=[mod]) as active, \
                 mock.patch("plugins.ds1.mod_loader._compose_params",
                            return_value=(b"merged", [])) as compose:
                context = tweak_mods.BuildContext({}, game, game)
                self.assertEqual(context.game_params(), b"merged")
                self.assertEqual(context.game_params(), b"merged")
            compose.assert_called_once_with(b"vanilla", [("A mod", b"mod")], conflicts_only=False)
            active.assert_called_once_with(game, only=frozenset({relative}))
