"""Enabled tweak builds preflight dependencies and restore failed batches."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from core import script_mods
from plugins.ff8 import tweak_mods


class TweakBuildTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.library = self.root / "library"
        self.library.mkdir()
        patcher = mock.patch.dict(os.environ, {script_mods.TRUST_ENV: str(self.root / "trust.json")})
        patcher.start()
        self.addCleanup(patcher.stop)

    def mod(self, name, code, **schema):
        root = self.library / name
        (root / "script").mkdir(parents=True)
        (root / "mod.json").write_text(json.dumps({"id": name, "name": name,
            "enabled": True, "script": {"version": 1}}), encoding="utf-8")
        (root / "script/__init__.py").write_text("", encoding="utf-8")
        (root / "script/tweak.py").write_text(code, encoding="utf-8")
        (root / "settings.schema.json").write_text(json.dumps(schema), encoding="utf-8")
        script_mods.set_trusted(root, True)
        return root

    def build(self):
        return tweak_mods.build_enabled(self.project, self.library, self.root / "game", self.root / "baseline")

    def test_later_script_failure_restores_previous_outputs_and_manifest(self):
        first = self.mod("a", "def build(settings, context):\n"
            "    if settings['new']:\n"
            "        return {'hext/change.txt': 'new', 'direct/new.bin': b'new'}\n"
            "    return {'hext/change.txt': 'old', 'direct/removed.bin': b'old'}\n",
            fields=[{"key": "new", "type": "bool", "default": False}])
        script_mods.build(first, None, allowed_roots=tweak_mods.ALLOWED_ROOTS)
        manifest = (first / script_mods.MANIFEST_FILE).read_bytes()
        script_mods.save_values(first, {"new": True})
        self.mod("b", "def build(settings, context):\n    raise ValueError('broken script')\n")
        with self.assertRaisesRegex(tweak_mods.BuildError, "b: broken script"):
            self.build()
        self.assertEqual((first / "hext/change.txt").read_text(), "old")
        self.assertEqual((first / "direct/removed.bin").read_bytes(), b"old")
        self.assertFalse((first / "direct/new.bin").exists())
        self.assertEqual((first / script_mods.MANIFEST_FILE).read_bytes(), manifest)

    def test_failed_batch_removes_a_first_build_outputs_and_manifest(self):
        first = self.mod("a", "def build(settings, context):\n    return {'hext/a.txt': 'new'}\n")
        self.mod("b", "def build(settings, context):\n    raise ValueError('broken script')\n")
        with self.assertRaises(tweak_mods.BuildError):
            self.build()
        self.assertFalse((first / "hext/a.txt").exists())
        self.assertFalse((first / script_mods.MANIFEST_FILE).exists())

    def test_conflicts_and_missing_requirements_fail_before_any_build(self):
        self.mod("a", "def build(settings, context):\n    return {'hext/a.txt': 'new'}\n")
        second = self.mod("b", "def build(settings, context):\n    return {}\n")
        for schema, message in (({"conflicts": ["a"]}, "conflicts with a"),
                                ({"requires": ["absent"]}, "requires absent"),
                                ({"blocker": "unsupported"}, "unsupported")):
            (second / script_mods.SCHEMA_FILE).write_text(json.dumps(schema), encoding="utf-8")
            with mock.patch.object(script_mods, "build") as build:
                with self.assertRaisesRegex(tweak_mods.BuildError, message):
                    self.build()
                build.assert_not_called()

    def test_later_untrusted_mod_fails_before_any_build(self):
        self.mod("a", "def build(settings, context):\n    return {}\n")
        second = self.mod("b", "def build(settings, context):\n    return {}\n")
        script_mods.set_trusted(second, False)
        with mock.patch.object(script_mods, "build") as build:
            with self.assertRaisesRegex(tweak_mods.BuildError, "untrusted"):
                self.build()
            build.assert_not_called()

    def test_batch_rollback_failure_names_mod_and_original_error(self):
        self.mod("a", "def build(settings, context):\n    return {'hext/a.txt': 'new'}\n")
        self.mod("b", "def build(settings, context):\n    raise ValueError('broken script')\n")
        with mock.patch.object(script_mods, "restore_generated", side_effect=OSError("disk unavailable")):
            with self.assertRaisesRegex(tweak_mods.BuildError, "b: broken script; rollback failed: a: disk unavailable"):
                self.build()


if __name__ == "__main__":
    unittest.main()
