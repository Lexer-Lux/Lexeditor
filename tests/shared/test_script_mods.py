"""Tweak mods build only when trusted, and only into their own game files."""
from __future__ import annotations

import json
import os
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
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dir = Path(self.temp.name)
        patcher = mock.patch.dict(os.environ, {script_mods.TRUST_ENV: str(self.dir / "trust.json")})
        patcher.start()
        self.addCleanup(patcher.stop)
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

    def test_an_untrusted_mod_never_runs(self):
        with self.assertRaisesRegex(script_mods.ScriptModError, "not trusted"):
            self.build()
        self.assertFalse((self.mod / "hext").exists())

    def test_editing_the_script_revokes_trust_until_trusted_again(self):
        self.assertEqual(script_mods.set_trusted(self.mod, True), "trusted")
        (self.mod / "script" / "helper.py").write_text("line = lambda n: 'changed'\n", encoding="utf-8")
        self.assertEqual(script_mods.trust_state(self.mod), "changed")
        with self.assertRaisesRegex(script_mods.ScriptModError, "changed since"):
            self.build()
        self.assertEqual(script_mods.set_trusted(self.mod, True), "trusted")
        self.build()

    def test_build_writes_outputs_and_removes_ones_no_longer_produced(self):
        script_mods.set_trusted(self.mod, True)
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
        script_mods.set_trusted(self.mod, True)
        target = self.mod / "hext/ff8/en_nv/patch.txt"
        target.parent.mkdir(parents=True)
        target.write_text("mine", encoding="utf-8")
        with self.assertRaisesRegex(script_mods.ScriptModError, "not generated"):
            self.build()
        self.assertEqual(target.read_text(encoding="utf-8"), "mine")

    def test_outputs_stay_inside_the_allowed_game_roots(self):
        script_mods.set_trusted(self.mod, True)
        for bad in ("../escape.txt", "C:/x.txt", "mod.json", "settings.json", "script/tweak.py", "textures/x.png"):
            (self.mod / "script" / "tweak.py").write_text(
                f"def build(settings, context):\n    return {{{bad!r}: 'x'}}\n", encoding="utf-8")
            script_mods.set_trusted(self.mod, True)
            with self.assertRaises(script_mods.ScriptModError, msg=bad):
                self.build()
        self.assertFalse((self.dir / "library" / "escape.txt").exists())

    def test_two_mods_with_the_same_module_names_do_not_share_code(self):
        other = make_mod(self.dir / "library", "Other", "line = lambda n: 'other'\n")
        for root in (self.mod, other):
            script_mods.set_trusted(root, True)
            self.build(root)
        self.assertEqual((self.mod / "hext/ff8/en_nv/patch.txt").read_text(encoding="utf-8"), "00 = 0A")
        self.assertEqual((other / "hext/ff8/en_nv/patch.txt").read_text(encoding="utf-8"), "other")

    def test_catalog_row_reads_without_running_the_script(self):
        (self.mod / "script" / "tweak.py").write_text("raise SystemExit('ran')\n", encoding="utf-8")
        row = script_mods.catalog_row(self.mod)
        self.assertEqual(row["trust"], "untrusted")
        self.assertEqual(row["schema"]["requires"], ["other"])
        self.assertEqual(row["values"]["amount"], 10)

    def test_describe_and_clear(self):
        script_mods.set_trusted(self.mod, True)
        self.assertEqual(script_mods.describe(self.mod, None), {"amount": 10})
        self.build()
        self.assertEqual(script_mods.clear(self.mod), ["hext/ff8/en_nv/patch.txt"])
        self.assertFalse((self.mod / script_mods.MANIFEST_FILE).exists())


if __name__ == "__main__":
    unittest.main()
