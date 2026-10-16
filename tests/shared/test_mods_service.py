"""The shared Mods tab's backend: listing, switching, downloads and first run."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_lexmods import archive, module  # noqa: E402
from core import lexmods, mods_service  # noqa: E402
from core.desktop_host import HostApi  # noqa: E402

REPO = "Lexer-Lux/Lexers-Mod-For-Test"


class ModsServiceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.temp = Path(temp.name)
        self.game = self.temp / "library" / "test"
        self.game.mkdir(parents=True)
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

    def test_moving_rewrites_every_order_key_and_keeps_the_rest(self):
        self.make("First", name="First", order=10, enabled=True)
        self.make("Second", name="Second", order=20)
        last = self.make("Third", name="Third", order=30, enabled=True)
        moved = mods_service.move(self.game, str(last), -2)
        self.assertEqual(moved["name"], "Third")
        self.assertEqual([(row["name"], row["order"]) for row in mods_service.library_rows(self.game)],
                         [("Third", 10), ("First", 11), ("Second", 12)])
        stored = json.loads((last / "mod.json").read_text())
        self.assertEqual(stored, {"name": "Third", "order": 10, "enabled": True})

    def test_moving_past_either_end_lands_on_that_end_and_zero_changes_nothing(self):
        first = self.make("First", name="First", order=1)
        self.make("Second", name="Second", order=2)
        mods_service.move(self.game, str(first), -9)
        self.assertEqual([row["name"] for row in mods_service.library_rows(self.game)], ["First", "Second"])
        before = (first / "mod.json").read_text()
        mods_service.move(self.game, str(first), 0)
        self.assertEqual((first / "mod.json").read_text(), before)
        mods_service.move(self.game, str(first), 9)
        self.assertEqual([(row["name"], row["order"]) for row in mods_service.library_rows(self.game)],
                         [("Second", 1), ("First", 2)])

    def test_moving_an_unnamed_mod_still_moves_it(self):
        self.make("Named", name="Named", order=1)
        unnamed = self.make("Unnamed")
        mods_service.move(self.game, str(unnamed), -1)
        self.assertEqual([row["folder"] for row in mods_service.library_rows(self.game)], ["Unnamed", "Named"])
        self.assertEqual(json.loads((unnamed / "mod.json").read_text()), {"order": 1})

    def test_moving_rejects_outside_folders_and_fractional_places(self):
        mine = self.make("Mine", name="Mine", order=1)
        for bad in (self.game, self.temp, self.game / "missing"):
            with self.assertRaises(ValueError):
                mods_service.move(self.game, str(bad), 1)
        for bad in ("1", 1.5, True, None):
            with self.assertRaises(ValueError):
                mods_service.move(self.game, str(mine), bad)

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


    def test_mod_files_lists_every_file_with_human_sizes(self):
        mod = self.make("Mine", name="Mine")
        (mod / "data").mkdir()
        (mod / "data" / "patch.parambnd").write_bytes(b"x" * 1536)
        (mod / "notes.txt").write_bytes(b"read me")
        result = mods_service.mod_files(mod)
        self.assertFalse(result["truncated"])
        by_name = {entry["relative"]: entry for entry in result["files"]}
        self.assertEqual(sorted(by_name), ["data/patch.parambnd", "mod.json", "notes.txt"])
        self.assertEqual(by_name["data/patch.parambnd"]["size"], 1536)
        self.assertEqual(by_name["data/patch.parambnd"]["sizeLabel"], "1.5 KB")
        self.assertEqual(by_name["notes.txt"]["sizeLabel"], "7 B")
        self.assertTrue(all(entry["loaded"] is False for entry in result["files"]))

    def test_mod_files_skips_symlinks_outside_the_folder(self):
        mod = self.make("Mine", name="Mine")
        outside = self.temp / "outside.txt"
        outside.write_text("elsewhere", encoding="utf-8")
        try:
            (mod / "sneaky.txt").symlink_to(outside)
        except OSError:
            self.skipTest("symlinks need privileges on this machine")
        result = mods_service.mod_files(mod)
        self.assertEqual([entry["relative"] for entry in result["files"]], ["mod.json"])

    def test_mod_files_stops_at_two_thousand(self):
        mod = self.make("Mine", name="Mine")
        for index in range(2005):
            (mod / f"file-{index:04d}.bin").write_bytes(b"x")
        result = mods_service.mod_files(mod)
        self.assertTrue(result["truncated"])
        self.assertEqual(len(result["files"]), 2000)

    def test_human_size_spells_bytes_through_gigabytes(self):
        sizes = {0: "0 B", 512: "512 B", 1024: "1 KB", 1536: "1.5 KB",
                 1024 ** 2: "1 MB", 3 * 1024 ** 3: "3 GB"}
        for size, label in sizes.items():
            self.assertEqual(mods_service._human_size(size), label)


class ModContentsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.library = Path(temp.name) / "library" / "test"
        self.library.mkdir(parents=True)
        self.mod = self.library / "Mine"
        self.mod.mkdir()
        (self.mod / "mod.json").write_text(json.dumps({"name": "Mine"}), encoding="utf-8")
        (self.mod / "data").mkdir()
        (self.mod / "data" / "patch.parambnd").write_bytes(b"x" * 100)

    def host(self, adapter, game=None):
        host = HostApi.__new__(HostApi)
        host._mod_library_lock = threading.RLock()
        host._game_mods = lambda _plugin: self.library
        host._mod_adapter = lambda _plugin: adapter
        root = str(game) if game else ""
        host._installations = SimpleNamespace(snapshot=lambda _plugin: {"root": root})
        return host

    def contents(self, adapter, game=None):
        return HostApi.mod_contents(self.host(adapter, game), "test", str(self.mod))

    def test_files_list_without_a_describing_loader(self):
        result = self.contents(None)
        self.assertEqual([entry["relative"] for entry in result["files"]],
                         ["data/patch.parambnd", "mod.json"])
        self.assertEqual(result["changes"], [])
        self.assertFalse(result["canDescribe"])
        self.assertIn("not available for this game", result["note"])

    def test_loader_without_describe_changes_lists_files_and_says_so(self):
        result = self.contents(SimpleNamespace())
        self.assertEqual(len(result["files"]), 2)
        self.assertFalse(result["canDescribe"])
        self.assertIn("not available for this game", result["note"])

    def test_describe_marks_loaded_files_and_surfaces_its_note(self):
        change = {"table": "Items", "id": 100, "label": "Stone", "fields": ["price"],
                  "added": False, "removed": False}
        adapter = SimpleNamespace(describe_changes=lambda folder, game: {
            "changes": [change], "truncated": False, "loaded": ["DATA/PATCH.PARAMBND"],
            "note": "compared against vanilla"})
        result = self.contents(adapter, game=self.library)
        self.assertTrue(result["canDescribe"])
        self.assertEqual(result["changes"], [change])
        self.assertFalse(result["changesTruncated"])
        self.assertEqual(result["note"], "compared against vanilla")
        by_name = {entry["relative"]: entry for entry in result["files"]}
        self.assertTrue(by_name["data/patch.parambnd"]["loaded"])
        self.assertFalse(by_name["mod.json"]["loaded"])

    def test_a_broken_describe_leaves_files_and_reports_the_error(self):
        def broken(folder, game):
            raise OSError("the archive cannot be read")
        result = self.contents(SimpleNamespace(describe_changes=broken), game=self.library)
        self.assertTrue(result["canDescribe"])
        self.assertEqual(result["changes"], [])
        self.assertEqual(result["note"], "the archive cannot be read")
        self.assertEqual(len(result["files"]), 2)

    def test_truncation_passes_through(self):
        adapter = SimpleNamespace(describe_changes=lambda folder, game: {
            "changes": [], "truncated": True, "loaded": [], "note": ""})
        result = self.contents(adapter, game=self.library)
        self.assertTrue(result["changesTruncated"])
        self.assertEqual(result["note"], "")

    def test_a_mod_outside_the_library_is_refused(self):
        with self.assertRaisesRegex(ValueError, "this game's library"):
            HostApi.mod_contents(self.host(None), "test", str(self.library.parent))


if __name__ == "__main__":
    unittest.main()
