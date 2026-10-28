"""Tweak mods build when enabled, and only into their own game files."""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from core import script_mods

TWEAK = '''
from . import helper

def build(settings, context):
    if not settings["enabled"]:
        return {}
    files = {"hext/ff8/en_nv/patch.txt": helper.line(settings["amount"])}
    if settings["amount"] > 50:
        files["direct/extra.bin"] = bytes([settings["amount"]])
    context.append(settings["amount"])
    return files

def describe(settings, context):
    return {"amount": settings["amount"]}
'''
SCHEMA = {"title": "Example", "help": "Does a thing.", "requires": ["other"], "fields": [
    {"key": "enabled", "type": "bool", "default": True},
    {"key": "amount", "type": "int", "default": 10, "min": 0, "max": 100},
    {"key": "mode", "type": "enum", "default": "a", "choices": [{"value": "a"}, {"value": "b"}]},
]}


def make_mod(parent: Path, name: str = "Example", helper_text: str = "line = lambda n: f'00 = {n:02X}'\n") -> Path:
    root = parent / name
    (root / "script").mkdir(parents=True)
    (root / "script" / "__init__.py").write_text("", encoding="utf-8")
    (root / "script" / "tweak.py").write_text(TWEAK, encoding="utf-8")
    (root / "script" / "helper.py").write_text(helper_text, encoding="utf-8")
    (root / "mod.json").write_text(json.dumps({"id": name.lower(), "name": name, "script": {"version": 1}}), encoding="utf-8")
    (root / "settings.schema.json").write_text(json.dumps(SCHEMA), encoding="utf-8")
    return root


class ScriptModTests(unittest.TestCase):
    def test_integer_tables_bound_entry_count_and_each_cost(self):
        field = {"key": "costs", "type": "intList", "min": 1, "max": 7,
                 "minLength": 0, "maxLength": 99}
        self.assertEqual(script_mods._coerce(field, []), [])
        self.assertEqual(script_mods._coerce(field, [1, 3, 7]), [1, 3, 7])
        for invalid in ([1]*100, [0], [8], [1.5]):
            with self.assertRaises(script_mods.ScriptModError):
                script_mods._coerce(field, invalid)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dir = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.mod = make_mod(self.dir / "library")

    def build(self, root=None):
        seen = []
        result = script_mods.build(root or self.mod, seen, allowed_roots=("hext", "direct"))
        return result, seen

    def test_recognises_a_tweak_mod_and_its_own_files(self):
        self.assertTrue(script_mods.is_script_mod(self.mod))
        self.assertTrue(script_mods.owns("script/tweak.py"))
        self.assertTrue(script_mods.owns("settings.json"))
        self.assertFalse(script_mods.owns("hext/ff8/en_nv/patch.txt"))
        self.assertFalse(script_mods.owns("direct/settings.json"))
        # Game archives under script/ (DS1 talk and AI scripts) stay game files.
        self.assertTrue(script_mods.owns("script/humanity_x64.S"))
        self.assertFalse(script_mods.owns("script/talk/m10_02_00_00.talkesdbnd.dcx"))
        self.assertFalse(script_mods.owns("script/m10_00_00_00.luabnd.DCX"))

    def test_values_start_at_defaults_and_bad_stored_values_fall_back(self):
        self.assertEqual(script_mods.values(self.mod), {"enabled": True, "amount": 10, "mode": "a"})
        (self.mod / "settings.json").write_text(json.dumps({"values": {"amount": 500, "mode": "b"}}), encoding="utf-8")
        self.assertEqual(script_mods.values(self.mod), {"enabled": True, "amount": 10, "mode": "b"})

    def test_saving_validates_every_value(self):
        self.assertEqual(script_mods.save_values(self.mod, {"amount": 60})["amount"], 60)
        for bad in ({"amount": 101}, {"amount": 1.5}, {"amount": True}, {"enabled": 1},
                    {"mode": "c"}, {"unknown": 1}):
            with self.assertRaises(script_mods.ScriptModError, msg=bad):
                script_mods.save_values(self.mod, bad)
        self.assertEqual(script_mods.values(self.mod)["amount"], 60)

    def test_a_mod_builds_with_no_trust_step(self):
        result, seen = self.build()
        self.assertEqual(seen, [10])
        self.assertEqual(result["files"], ["hext/ff8/en_nv/patch.txt"])

    def test_editing_the_script_changes_the_next_build(self):
        self.build()
        self.assertEqual((self.mod / "hext/ff8/en_nv/patch.txt").read_text(encoding="utf-8"), "00 = 0A")
        (self.mod / "script" / "helper.py").write_text("line = lambda n: 'changed'\n", encoding="utf-8")
        self.build()
        self.assertEqual((self.mod / "hext/ff8/en_nv/patch.txt").read_text(encoding="utf-8"), "changed")

    def test_build_writes_outputs_and_removes_ones_no_longer_produced(self):
        script_mods.save_values(self.mod, {"amount": 60})
        result, seen = self.build()
        self.assertEqual(seen, [60])
        self.assertEqual(result["files"], ["direct/extra.bin", "hext/ff8/en_nv/patch.txt"])
        self.assertEqual((self.mod / "hext/ff8/en_nv/patch.txt").read_text(encoding="utf-8"), "00 = 3C")
        script_mods.save_values(self.mod, {"amount": 5})
        result, _ = self.build()
        self.assertEqual(result["removed"], ["direct/extra.bin"])
        self.assertFalse((self.mod / "direct/extra.bin").exists())
        script_mods.save_values(self.mod, {"enabled": False})
        self.build()
        self.assertFalse((self.mod / "hext/ff8/en_nv/patch.txt").exists())

    def test_a_hand_made_file_is_never_overwritten(self):
        target = self.mod / "hext/ff8/en_nv/patch.txt"
        target.parent.mkdir(parents=True)
        target.write_text("mine", encoding="utf-8")
        with self.assertRaisesRegex(script_mods.ScriptModError, "not generated"):
            self.build()
        self.assertEqual(target.read_text(encoding="utf-8"), "mine")

    def test_outputs_stay_inside_the_allowed_game_roots(self):
        for bad in ("../escape.txt", "C:/x.txt", "mod.json", "settings.json", "script/tweak.py", "textures/x.png"):
            (self.mod / "script" / "tweak.py").write_text(
                f"def build(settings, context):\n    return {{{bad!r}: 'x'}}\n", encoding="utf-8")
            with self.assertRaises(script_mods.ScriptModError, msg=bad):
                self.build()
        self.assertFalse((self.dir / "library" / "escape.txt").exists())

    def test_two_mods_with_the_same_module_names_do_not_share_code(self):
        other = make_mod(self.dir / "library", "Other", "line = lambda n: 'other'\n")
        for root in (self.mod, other):
            self.build(root)
        self.assertEqual((self.mod / "hext/ff8/en_nv/patch.txt").read_text(encoding="utf-8"), "00 = 0A")
        self.assertEqual((other / "hext/ff8/en_nv/patch.txt").read_text(encoding="utf-8"), "other")

    def test_catalog_row_reads_without_running_the_script(self):
        (self.mod / "script" / "tweak.py").write_text("raise SystemExit('ran')\n", encoding="utf-8")
        row = script_mods.catalog_row(self.mod)
        self.assertNotIn("trust", row)
        self.assertEqual(row["schema"]["requires"], ["other"])
        self.assertEqual(row["values"]["amount"], 10)

    def test_describe_and_clear(self):
        self.assertEqual(script_mods.describe(self.mod, None), {"amount": 10})
        self.build()
        self.assertEqual(script_mods.clear(self.mod), ["hext/ff8/en_nv/patch.txt"])
        self.assertFalse((self.mod / script_mods.MANIFEST_FILE).exists())

    def test_manifest_paths_are_validated_before_any_files_change(self):
        self.build()
        patch = self.mod / "hext/ff8/en_nv/patch.txt"
        original = patch.read_bytes()
        outside = self.mod.parent / "outside.txt"
        outside.write_bytes(b"keep")
        manifest = self.mod / script_mods.MANIFEST_FILE
        for bad in ("../outside.txt", str(outside.resolve()), "MOD.JSON", "script/tweak.py"):
            manifest.write_text(json.dumps({"version": 1, "files": {
                "hext/ff8/en_nv/patch.txt": hashlib.sha256(original).hexdigest(),
                bad: hashlib.sha256(b"keep").hexdigest(),
            }}), encoding="utf-8")
            script_mods.save_values(self.mod, {"amount": 60})
            for operation in (self.build, lambda: script_mods.clear(self.mod)):
                with self.assertRaises(script_mods.ScriptModError, msg=bad):
                    operation()
                self.assertEqual(patch.read_bytes(), original)
                self.assertEqual(outside.read_bytes(), b"keep")
                self.assertFalse((self.mod / "direct/extra.bin").exists())

    def test_malformed_manifest_is_refused_before_writing(self):
        manifest = self.mod / script_mods.MANIFEST_FILE
        for malformed in (None, [], {}, {"version": 2, "files": {}},
                          {"version": 1, "files": []},
                          {"version": 1, "files": {"hext/a.txt": "not a hash"}}):
            manifest.write_text(json.dumps(malformed), encoding="utf-8")
            for operation in (self.build, lambda: script_mods.clear(self.mod)):
                with self.assertRaises(script_mods.ScriptModError):
                    operation()
            self.assertFalse((self.mod / "hext").exists())
            self.assertEqual(json.loads(manifest.read_text()), malformed)

    def test_hand_edits_to_generated_files_are_overwritten_on_rebuild_removal_and_clear(self):
        # A rebuild always comes from the mod's script (generated-file guard
        # dropped in cdb352a0): edits to its output are replaced, not refused.
        script_mods.save_values(self.mod, {"amount": 60})
        self.build()
        extra = self.mod / "direct/extra.bin"
        patch = self.mod / "hext/ff8/en_nv/patch.txt"
        manifest = self.mod / script_mods.MANIFEST_FILE
        extra.write_bytes(b"my changes")
        patch.write_bytes(b"my changes")
        script_mods.save_values(self.mod, {"amount": 70})
        self.build()
        self.assertEqual(extra.read_bytes(), bytes([70]))
        self.assertEqual(patch.read_text(encoding="utf-8"), "00 = 46")
        extra.write_bytes(b"my changes")
        script_mods.save_values(self.mod, {"amount": 5})
        self.build()
        self.assertFalse(extra.exists())
        self.assertEqual(patch.read_text(encoding="utf-8"), "00 = 05")
        patch.write_bytes(b"my changes")
        self.assertEqual(script_mods.clear(self.mod), ["hext/ff8/en_nv/patch.txt"])
        self.assertFalse(patch.exists())
        self.assertFalse(manifest.exists())

    def test_generated_paths_cannot_follow_a_directory_link_outside_the_mod(self):
        outside = self.dir / "outside"
        outside.mkdir()
        try:
            (self.mod / "hext").symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("Directory symlinks are unavailable for this account")
        with self.assertRaisesRegex(script_mods.ScriptModError, "outside"):
            self.build()
        target = outside / "keep.txt"
        target.write_bytes(b"keep")
        (self.mod / script_mods.MANIFEST_FILE).write_text(json.dumps({"version": 1,
            "files": {"hext/keep.txt": hashlib.sha256(b"keep").hexdigest()}}), encoding="utf-8")
        with self.assertRaisesRegex(script_mods.ScriptModError, "outside"):
            script_mods.clear(self.mod)
        self.assertEqual(target.read_bytes(), b"keep")

    def test_partial_write_failure_restores_files_and_manifest(self):
        self.build()
        patch = self.mod / "hext/ff8/en_nv/patch.txt"
        manifest = self.mod / script_mods.MANIFEST_FILE
        old_patch, old_manifest = patch.read_bytes(), manifest.read_bytes()
        script_mods.save_values(self.mod, {"amount": 60})
        write = script_mods.atomic_write

        def fail_manifest(path, data):
            if path == manifest:
                raise OSError("simulated manifest failure")
            write(path, data)

        with mock.patch.object(script_mods, "atomic_write", side_effect=fail_manifest):
            with self.assertRaisesRegex(OSError, "simulated manifest failure"):
                self.build()
        self.assertEqual(patch.read_bytes(), old_patch)
        self.assertEqual(manifest.read_bytes(), old_manifest)
        self.assertFalse((self.mod / "direct/extra.bin").exists())

    def test_partial_removal_failure_restores_removed_files(self):
        script_mods.save_values(self.mod, {"amount": 60})
        self.build()
        extra = self.mod / "direct/extra.bin"
        script_mods.save_values(self.mod, {"amount": 5})
        write = script_mods.atomic_write

        def fail_manifest(path, data):
            if path.name == script_mods.MANIFEST_FILE:
                raise OSError("simulated manifest failure")
            write(path, data)

        with mock.patch.object(script_mods, "atomic_write", side_effect=fail_manifest):
            with self.assertRaises(OSError):
                self.build()
        self.assertEqual(extra.read_bytes(), bytes([60]))
        self.assertEqual((self.mod / "hext/ff8/en_nv/patch.txt").read_text(), "00 = 3C")

    def test_failed_rollback_is_reported_with_original_failure(self):
        self.build()
        script_mods.save_values(self.mod, {"amount": 60})
        write = script_mods.atomic_write
        count = 0

        def fail_after_first_write(path, data):
            nonlocal count
            count += 1
            if count > 1:
                raise OSError("disk unavailable")
            write(path, data)

        with mock.patch.object(script_mods, "atomic_write", side_effect=fail_after_first_write):
            with self.assertRaisesRegex(script_mods.ScriptModError, "Build failed: disk unavailable; .*rollback failed"):
                self.build()


if __name__ == "__main__":
    unittest.main()
