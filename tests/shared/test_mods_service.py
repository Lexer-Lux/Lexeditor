"""The shared Mods tab's backend: listing, switching, downloads and first run."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_lexmods import archive, module  # noqa: E402
from core import lexmods, mods_service, script_mods  # noqa: E402

REPO = "Lexer-Lux/Lexers-Mod-For-Test"


class ModsServiceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.temp = Path(temp.name)
        self.game = self.temp / "library" / "test"
        self.game.mkdir(parents=True)
        patcher = mock.patch.dict(os.environ, {script_mods.TRUST_ENV: str(self.temp / "trust.json")})
        patcher.start()
        self.addCleanup(patcher.stop)
        mods_service._catalogs.clear()

    def make(self, folder, **mod):
        root = self.game / folder
        root.mkdir()
        if mod:
            (root / "mod.json").write_text(json.dumps(mod), encoding="utf-8")
        return root

    def test_local_mods_come_first_then_lexer_modules_not_downloaded(self):
        self.make("Mine", name="Mine", author="Me", enabled=True)
        self.make("Unnamed")
        (self.game / ".lexmod-staging").mkdir()
        lexmods.install(REPO, self.game, modules=["Combat"],
                        fetch={"version": {"version": "v1", "ref": "v1", "zip": ""},
                               "zip": archive({"Combat": module("Combat"), "Extra": module("Extra")})})
        remote = {"version": "v1", "modules": [{"folder": "Combat", "name": "Combat", "author": "Lexer", "description": "", "enabled": True},
                                               {"folder": "Extra", "name": "Extra", "author": "Lexer", "description": "x", "enabled": False}]}
        with mock.patch.object(lexmods, "catalog", return_value=remote):
            result = mods_service.overview(self.game, REPO)
        names = [row["name"] for row in result["rows"]]
        self.assertEqual(sorted(names), ["Combat", "Mine", "Unnamed"])
        unnamed = next(row for row in result["rows"] if row["folder"] == "Unnamed")
        self.assertEqual(unnamed["missing"], ["name"])
        combat = next(row for row in result["rows"] if row["folder"] == "Combat")
        self.assertEqual(combat["lexmod"]["version"], "v1")
        self.assertEqual([row["folder"] for row in result["remote"]], ["Extra"])
        self.assertTrue(result["remote"][0]["remote"])

    def test_an_unreachable_lexmod_still_lists_local_mods(self):
        self.make("Mine", name="Mine")
        with mock.patch.object(lexmods, "catalog", side_effect=lexmods.LexmodError("not published")):
            result = mods_service.overview(self.game, REPO)
        self.assertEqual([row["name"] for row in result["rows"]], ["Mine"])
        self.assertEqual(result["lexmod"]["error"], "not published")
        self.assertEqual(result["remote"], [])

    def test_only_this_games_mod_folders_can_be_touched(self):
        mine = self.make("Mine", name="Mine")
        self.assertEqual(mods_service.checked_mod(self.game, str(mine)), mine.resolve())
        for bad in (self.game, self.temp, self.game / "missing", self.game / ".lexmod-x"):
            with self.assertRaises(ValueError):
                mods_service.checked_mod(self.game, str(bad))

    def test_switching_keeps_other_keys_and_needs_a_name(self):
        mine = self.make("Mine", name="Mine", order=4)
        mods_service.set_enabled(mine, True)
        self.assertEqual(json.loads((mine / "mod.json").read_text()), {"name": "Mine", "order": 4, "enabled": True})
        with self.assertRaises(ValueError):
            mods_service.set_enabled(self.make("Unnamed"), True)
        with self.assertRaises(ValueError):
            mods_service.set_enabled(mine, "yes")

    def test_back_undoes_a_finished_download_and_stops_a_running_one(self):
        downloads = mods_service.Downloads()
        payload = {"version": {"version": "v1", "ref": "v1", "zip": ""}, "zip": archive({"Combat": module("Combat")})}
        real = lexmods.install
        with mock.patch.object(lexmods, "install", lambda *a, **k: real(*a, fetch=payload, **k)):
            downloads.start("test", REPO, self.game)
            for _ in range(100):
                if downloads.progress("test")["state"] != "running":
                    break
                time.sleep(0.02)
        self.assertEqual(downloads.progress("test")["state"], "done")
        self.assertTrue((self.game / "Combat").is_dir())
        self.assertEqual(downloads.cancel("test")["state"], "cancelled")
        self.assertFalse((self.game / "Combat").exists())

        started = threading.Event()

        def slow(*args, cancel=None, **kwargs):
            started.set()
            cancel.wait(5)
            raise lexmods.Cancelled("cancelled")
        with mock.patch.object(lexmods, "install", slow):
            downloads.start("test", REPO, self.game)
            started.wait(5)
            downloads.cancel("test")
            for _ in range(100):
                if downloads.progress("test")["state"] != "running":
                    break
                time.sleep(0.02)
        self.assertEqual(downloads.progress("test")["state"], "cancelled")

    def test_updates_run_at_most_hourly_and_only_with_downloaded_modules(self):
        state = self.temp / "updates.json"
        self.assertEqual(mods_service.update_if_due(REPO, self.game, state), {"updated": False})
        lexmods.install(REPO, self.game, fetch={"version": {"version": "v1", "ref": "v1", "zip": ""},
                                                "zip": archive({"Combat": module("Combat")})})
        with mock.patch.object(lexmods, "latest", return_value={"version": "v2", "ref": "v2", "zip": ""}), \
                mock.patch.object(lexmods, "install", return_value={"version": "v2", "installed": ["Combat"]}) as install:
            self.assertTrue(mods_service.update_if_due(REPO, self.game, state)["updated"])
            self.assertEqual(install.call_args.kwargs["modules"], [])
            self.assertEqual(mods_service.update_if_due(REPO, self.game, state), {"updated": False})

    def test_first_run_is_shown_once_per_game(self):
        onboarding = mods_service.Onboarding(self.temp / "onboarding.json")
        self.assertFalse(onboarding.seen("ff8"))
        onboarding.finish("ff8")
        onboarding.finish("ff8")
        self.assertTrue(onboarding.seen("ff8"))
        self.assertFalse(onboarding.seen("ds1"))
        self.assertEqual(json.loads((self.temp / "onboarding.json").read_text()), {"done": ["ff8"]})


if __name__ == "__main__":
    unittest.main()
