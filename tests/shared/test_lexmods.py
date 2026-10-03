"""Lexer's Mods: the README contract, and installing modules safely.

Archives are built in memory in GitHub's zipball layout, so no network is used.
"""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock
import zipfile

from core import lexmods, script_mods

README = f"""# Lexer's Mod for Test

Intro text.

## Features

- Better combat
- A long feature that
  wraps onto a second line
- {lexmods.FINAL_FEATURE}

## Installing

- not a feature
"""


def archive(modules: dict[str, dict[str, object]], top="Lexer-Lux-Lexers-Mod-For-Test-abc123") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zipped:
        zipped.writestr(f"{top}/README.md", README)
        for folder, files in modules.items():
            for name, content in files.items():
                data = json.dumps(content) if isinstance(content, dict) else content
                zipped.writestr(f"{top}/{folder}/{name}", data)
    return buffer.getvalue()


def module(name, enabled=True, extra=None, settings=None):
    files = {"mod.json": {"name": name, "author": "Lexer", "enabled": enabled, **(extra or {})},
             "data/thing.txt": f"{name} data"}
    if settings is not None:
        files["settings.json"] = {"values": settings}
    return files


def fetch(version, modules):
    return {"version": {"version": version, "ref": version, "zip": "unused"}, "zip": archive(modules)}


class ReadmeContractTests(unittest.TestCase):
    def test_features_are_read_in_order_and_end_with_the_customisable_line(self):
        self.assertEqual(lexmods.features(README), ["Better combat", "A long feature that wraps onto a second line",
                                                   lexmods.FINAL_FEATURE])
        self.assertEqual(lexmods.readme_problems(README), [])

    def test_contract_problems(self):
        self.assertTrue(lexmods.readme_problems("# Mod\n\nNo features here."))
        self.assertTrue(lexmods.readme_problems("## Features\n\n- Better combat\n"))
        self.assertTrue(lexmods.readme_problems(f"## Features\n\n- {lexmods.FINAL_FEATURE}\n"))


class InstallTests(unittest.TestCase):
    REPO = "Lexer-Lux/Lexers-Mod-For-Test"

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.library = Path(temp.name) / "test"
        patcher = mock.patch.dict(os.environ, {script_mods.TRUST_ENV: str(Path(temp.name) / "trust.json")})
        patcher.start()
        self.addCleanup(patcher.stop)

    def install(self, version, upstream, **kwargs):
        return lexmods.install(self.REPO, self.library, fetch=fetch(version, upstream), **kwargs)

    def test_first_install_brings_every_module_with_its_defaults(self):
        result = self.install("v1", {"Combat": module("Combat", settings={"x": 1}), "Extra": module("Extra", enabled=False)})
        self.assertEqual(result["installed"], ["Combat", "Extra"])
        self.assertEqual(json.loads((self.library / "Extra" / "mod.json").read_text())["enabled"], False)
        self.assertEqual(json.loads((self.library / "Combat" / "settings.json").read_text()), {"values": {"x": 1}})
        self.assertEqual(set(lexmods.installed(self.library, self.REPO)), {"Combat", "Extra"})

    def test_one_module_can_be_downloaded_on_its_own(self):
        self.install("v1", {"Combat": module("Combat"), "Extra": module("Extra")}, modules=["Extra"])
        self.assertEqual(sorted(p.name for p in self.library.iterdir()), ["Extra"])

    def test_an_update_replaces_files_but_keeps_settings_and_switches(self):
        self.install("v1", {"Combat": module("Combat", settings={"x": 1})})
        (self.library / "Combat" / "settings.json").write_text(json.dumps({"values": {"x": 9}}))
        stored = json.loads((self.library / "Combat" / "mod.json").read_text())
        (self.library / "Combat" / "mod.json").write_text(json.dumps({**stored, "enabled": False}))
        updated = module("Combat", settings={"x": 1})
        updated["data/thing.txt"] = "new data"
        self.install("v2", {"Combat": updated, "New": module("New")}, modules=[])
        combat = self.library / "Combat"
        self.assertEqual((combat / "data" / "thing.txt").read_text(), "new data")
        self.assertEqual(json.loads((combat / "settings.json").read_text()), {"values": {"x": 9}})
        self.assertIs(json.loads((combat / "mod.json").read_text())["enabled"], False)
        self.assertEqual(lexmods.installed(self.library, self.REPO)["Combat"]["version"], "v2")
        self.assertFalse((self.library / "New").exists(), "an update brings no module the reader did not download")

    def test_a_mod_lexer_did_not_install_is_never_overwritten(self):
        (self.library / "Combat").mkdir(parents=True)
        (self.library / "Combat" / "mine.txt").write_text("mine")
        with self.assertRaisesRegex(lexmods.LexmodError, "did not come from Lexer's mod"):
            self.install("v1", {"Combat": module("Combat")})
        self.assertEqual(sorted(p.name for p in (self.library / "Combat").iterdir()), ["mine.txt"])

    def test_cancelling_installs_nothing(self):
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(lexmods.Cancelled):
            self.install("v1", {"Combat": module("Combat")}, cancel=cancel)
        self.assertEqual([p.name for p in self.library.iterdir()], [])

    def test_script_modules_are_trusted_and_removal_touches_only_lexmod_modules(self):
        tweak = module("Tweak", extra={"script": {"version": 1}})
        tweak["script/__init__.py"] = ""
        tweak["script/tweak.py"] = "def build(settings, context):\n    return {}\n"
        self.install("v1", {"Tweak": tweak})
        self.assertEqual(script_mods.trust_state(self.library / "Tweak"), "trusted")
        (self.library / "Mine").mkdir()
        self.assertEqual(lexmods.remove(self.library, self.REPO, ["Tweak", "Mine"]), ["Tweak"])
        self.assertTrue((self.library / "Mine").is_dir())
        self.assertFalse((self.library / "Tweak").exists())

    def test_archive_paths_cannot_escape(self):
        with self.assertRaises(ValueError):
            self.install("v1", {"Combat": {"mod.json": {"name": "x"}, "../escape.txt": "x"}})


if __name__ == "__main__":
    unittest.main()
