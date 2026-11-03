"""Rebuilding always comes from the mod's script; startup validation stays.

A hand edit to a generated file is overwritten by the next rebuild, never
refused: switching mods rebuilds from each mod's script without error. The
checks that protect the game from a wrong patch (exe_patches.validate and
the original-bytes checks behind the loader) still refuse.
"""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from core import script_mods
from plugins.ds1 import exe_patches
from plugins.ds1 import tweak_mods as ds1_tweaks

SCRIPT = '''
def build(settings, context):
    files = {"hext/ff8/en_nv/patch.txt": "built %d" % settings["amount"]}
    if settings["amount"] > 50:
        files["direct/extra.bin"] = bytes([settings["amount"]])
    return files
'''
SCHEMA = {"fields": [{"key": "amount", "type": "int", "default": 10, "min": 0, "max": 100}]}


def make_mod(parent: Path, name: str = "example") -> Path:
    root = parent / name
    (root / "script").mkdir(parents=True)
    (root / "script" / "__init__.py").write_text("", encoding="utf-8")
    (root / "script" / "tweak.py").write_text(SCRIPT, encoding="utf-8")
    (root / "mod.json").write_text(
        json.dumps({"id": name, "name": name, "script": {"version": 1}}), encoding="utf-8")
    (root / "settings.schema.json").write_text(json.dumps(SCHEMA), encoding="utf-8")
    return root


def batch_row(root: Path) -> dict:
    row = script_mods.catalog_row(root)
    row.update({"id": root.name, "name": root.name})
    return row


class RebuildAlwaysTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.mod = make_mod(self.dir / "library")

    def test_hand_modified_generated_file_is_rebuilt_from_the_script(self):
        script_mods.build(self.mod, None, allowed_roots=("hext", "direct"))
        patch = self.mod / "hext/ff8/en_nv/patch.txt"
        patch.write_text("my hand edit", encoding="utf-8")
        result = script_mods.build(self.mod, None, allowed_roots=("hext", "direct"))
        self.assertEqual(result["files"], ["hext/ff8/en_nv/patch.txt"])
        self.assertEqual(patch.read_text(encoding="utf-8"), "built 10")

    def test_hand_modified_file_no_longer_produced_is_removed(self):
        script_mods.save_values(self.mod, {"amount": 60})
        script_mods.build(self.mod, None, allowed_roots=("hext", "direct"))
        extra = self.mod / "direct/extra.bin"
        extra.write_bytes(b"my changes")
        script_mods.save_values(self.mod, {"amount": 5})
        result = script_mods.build(self.mod, None, allowed_roots=("hext", "direct"))
        self.assertEqual(result["removed"], ["direct/extra.bin"])
        self.assertFalse(extra.exists())

    def test_switch_path_rebuilds_hand_modified_files_without_error(self):
        script_mods.build(self.mod, None, allowed_roots=("hext", "direct"))
        patch = self.mod / "hext/ff8/en_nv/patch.txt"
        patch.write_text("my hand edit", encoding="utf-8")
        context = SimpleNamespace(current="")
        built = script_mods.build_batch(
            [batch_row(self.mod)], context, allowed_roots=("hext", "direct"))
        self.assertEqual(built, [{"id": self.mod.name, "files": ["hext/ff8/en_nv/patch.txt"]}])
        self.assertEqual(patch.read_text(encoding="utf-8"), "built 10")

    def test_clear_removes_hand_modified_generated_files(self):
        script_mods.build(self.mod, None, allowed_roots=("hext", "direct"))
        (self.mod / "hext/ff8/en_nv/patch.txt").write_text("my hand edit", encoding="utf-8")
        self.assertEqual(script_mods.clear(self.mod), ["hext/ff8/en_nv/patch.txt"])
        self.assertFalse((self.mod / "hext/ff8/en_nv/patch.txt").exists())
        self.assertFalse((self.mod / script_mods.MANIFEST_FILE).exists())


DS1_SCRIPT = '''
import json

def build(settings, context):
    return {"native/handedit.json": json.dumps({"version": 1})}
'''


def make_ds1_mod(library: Path) -> Path:
    root = library / "handedit"
    (root / "script").mkdir(parents=True)
    (root / "script" / "__init__.py").write_text("", encoding="utf-8")
    (root / "script" / "tweak.py").write_text(DS1_SCRIPT, encoding="utf-8")
    (root / "mod.json").write_text(json.dumps(
        {"id": "handedit", "name": "Handedit", "enabled": True, "order": 1,
         "script": {"version": 1}}), encoding="utf-8")
    return root


class Ds1SwitchRebuildTests(unittest.TestCase):
    def test_build_specs_rebuilds_a_hand_edited_patch_without_error(self):
        with tempfile.TemporaryDirectory() as temp:
            library = Path(temp) / "library"
            library.mkdir()
            make_ds1_mod(library)
            ds1_tweaks.build_specs(library)
            target = library / "handedit" / "native" / "handedit.json"
            target.write_text("my hand edit", encoding="utf-8")
            specs = ds1_tweaks.build_specs(library)
            self.assertEqual(len(specs), 1)
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"version": 1})


class StartupValidationTests(unittest.TestCase):
    def test_validate_still_refuses_a_wrong_patch(self):
        with self.assertRaises(exe_patches.PatchError):
            exe_patches.validate({"version": 99}, "Broken")
        with self.assertRaisesRegex(exe_patches.PatchError, "original instruction bytes"):
            exe_patches.validate(
                {"version": 1, "hooks": [{"rva": 0x1000, "original": "90", "bytes": "9090"}]},
                "Broken")

    def test_composer_still_refuses_a_non_vanilla_executable(self):
        with self.assertRaisesRegex(exe_patches.PatchError, "not the supported vanilla"):
            exe_patches.runtime_patch(b"not the game", [])


if __name__ == "__main__":
    unittest.main()
