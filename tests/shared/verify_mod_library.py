"""Headless checks for shared imports and the FF7R PAK adapter."""
from pathlib import Path
import json
import io
import hashlib
import sys
import tempfile
import unittest
from unittest.mock import patch
from unittest.mock import Mock
from types import SimpleNamespace
import threading
import zipfile
import urllib.request
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.mod_library import ModLibrary, documents_folder, package_root, relative_path
from plugins.ff7r.mod_support import PakModAdapter
from core.managed_mods import ManagedModSpec, update_mod, recover_update, refresh_active_mod, check_release


class ImportTests(unittest.TestCase):
    def test_editable_copy_service_save_reaches_deployed_pak(self):
        from plugins.ff7r.plugin import FF7RSession, _test_package
        from plugins.ff7r.tooling import pack_directory, get_file
        from plugins.ff7r.dataobject import DataObjectPackage
        from urllib.parse import quote
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            asset = "End/Content/GameContents/DataObject/Resident/Equipment.uasset"
            fixture = root / "fixture"
            target = fixture / asset
            target.parent.mkdir(parents=True)
            uasset, uexp = _test_package()
            target.write_bytes(uasset)
            target.with_suffix(".uexp").write_bytes(uexp)
            original = root / "original"
            original.mkdir()
            pack_directory(fixture, original / "source_P.pak", version="V4")
            adapter = PakModAdapter()
            library = ModLibrary(root / "library")
            copied = library.import_mod("ff7r", original, adapter, "Editable", prepare_editable=True)
            exe = root / "game/End/Binaries/Win64/ff7remake_.exe"
            exe.parent.mkdir(parents=True)
            exe.touch()
            (root / "game/End/Content/Paks").mkdir(parents=True)
            with FF7RSession({"LEXEDITOR_FF7R_ROOT": str(root / "game"),
                    "LEXEDITOR_FF7R_DATA_ROOT": str(root / "data"),
                    "LEXEDITOR_FF7R_PROJECT": str(copied),
                    "LEXEDITOR_FF7R_TEST_DATAOBJECTS": str(fixture)}) as session:
                def request(path, payload=None):
                    body = None if payload is None else json.dumps(payload).encode()
                    req = urllib.request.Request(session.url + path, data=body,
                        headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req) as response:
                        return json.load(response)
                catalog = request("api/catalog")
                selected = catalog["assets"][0]["asset"]
                data = request("api/data?asset=" + quote(selected, safe=""))
                request("api/save", {"asset": selected, "sourceSha256": data["sourceSha256"],
                    "activeSha256": data["activeSha256"],
                    "edits": [{"entry": 0, "property": "Power", "value": 99}]})
            adapter.activate([copied], root / "game")
            deployed = root / "game/End/Content/Paks/~mods/LexeditorLibrary/Editable_P.pak"
            reread = DataObjectPackage.from_bytes(get_file(deployed, asset),
                get_file(deployed, asset.replace(".uasset", ".uexp")))
            self.assertEqual(reread.entries[0].values["Power"], 99)
            unchanged = DataObjectPackage.from_bytes(get_file(original / "source_P.pak", asset),
                get_file(original / "source_P.pak", asset.replace(".uasset", ".uexp")))
            self.assertNotEqual(unchanged.entries[0].values["Power"], 99)

    def test_move_recovery_reopens_editor_after_commit(self):
        from core.desktop_host import HostApi
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, destination = root / "old", root / "new"
            source.mkdir()
            (source / "mod.txt").write_text("saved edit")
            records = []
            ModLibrary(source).relocate(destination, lambda target: None, journal=records.append)
            host = HostApi.__new__(HostApi)
            host._mod_library_lock = threading.RLock()
            host._plugin_id = "ff7r"
            host._dirty_count = 0
            host._session_uses_library = lambda path: True
            host.mod_library_location = lambda: {"root": str(source), "move": records[-1]}
            host._save_library_move = records.append
            host._settings = SimpleNamespace(set_mod_library_path=Mock())
            host._projects = SimpleNamespace(relocate_library=Mock())
            host.open_plugin = Mock(return_value={"url": "http://127.0.0.1:12345/"})
            result = host.recover_mod_library_move()
            self.assertEqual(result["url"], "http://127.0.0.1:12345/")
            host._projects.relocate_library.assert_called_once()
            host.open_plugin.assert_called_once_with("ff7r")
            host._dirty_count = 1
            host.open_plugin.reset_mock()
            with self.assertRaisesRegex(ValueError, "Save the current mod"):
                host.recover_mod_library_move()
            host.open_plugin.assert_not_called()

    def test_missing_release_explains_unavailable(self):
        with patch("core.managed_mods.release_request", side_effect=urllib.error.HTTPError(
                "https://api.github.com", 404, "Not Found", {}, None)):
            with self.assertRaisesRegex(ValueError, "No stable managed mod release"):
                check_release(ManagedModSpec("owner/mod", "mod.zip"))

    @patch("plugins.ff7r.mod_support.list_pak", return_value=["End/Content/Test.uasset"])
    def test_managed_update_refreshes_enabled_deployment(self, listing):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            library = ModLibrary(root / "library")
            spec = ManagedModSpec("owner/mod", "mod.zip")
            mod = library.root / "ff7r" / spec.folder_name
            mod.mkdir(parents=True)
            package = mod / "test_P.pak"
            package.write_bytes(b"version one")
            game = root / "game"
            exe = game / "End/Binaries/Win64/ff7remake_.exe"
            exe.parent.mkdir(parents=True)
            exe.touch()
            adapter = PakModAdapter()
            self.assertFalse(refresh_active_mod(library, "ff7r", adapter, spec, game))
            adapter.activate([mod], game)
            package.write_bytes(b"version two")
            self.assertTrue(refresh_active_mod(library, "ff7r", adapter, spec, game))
            deployed = game / "End/Content/Paks/~mods/LexeditorLibrary/test_P.pak"
            self.assertEqual(deployed.read_bytes(), b"version two")
            package.write_bytes(b"version three")
            with patch("plugins.ff7r.mod_support.shutil.copyfile", side_effect=OSError("copy failed")):
                with self.assertRaises(OSError):
                    refresh_active_mod(library, "ff7r", adapter, spec, game)
            self.assertEqual(deployed.read_bytes(), b"version two")
            self.assertTrue(refresh_active_mod(library, "ff7r", adapter, spec, game))
            self.assertEqual(deployed.read_bytes(), b"version three")
            adapter.activate([], game)
            self.assertFalse(refresh_active_mod(library, "ff7r", adapter, spec, game))

    def test_service_rejects_managed_save(self):
        from plugins.ff7r.plugin import FF7RSession
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture = root / "fixture"
            fixture.mkdir()
            (root / "game/End/Content/Paks").mkdir(parents=True)
            project = root / "project"
            project.mkdir()
            with FF7RSession({"LEXEDITOR_FF7R_ROOT": str(root / "game"),
                    "LEXEDITOR_FF7R_DATA_ROOT": str(root / "data"),
                    "LEXEDITOR_FF7R_PROJECT": str(project),
                    "LEXEDITOR_FF7R_TEST_DATAOBJECTS": str(fixture),
                    "LEXEDITOR_MOD_READ_ONLY": "1"}) as session:
                request = urllib.request.Request(session.url + "api/runtime/save", data=b'{"config":{}}',
                    headers={"Content-Type":"application/json"})
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(request)
                self.assertEqual(error.exception.code, 403)
                # A managed mod is locked because an update would replace a
                # direct edit, so the refusal asks for a copy. The no-mod lock
                # has its own wording, which the host marks with LEXEDITOR_NO_MOD.
                self.assertIn("editable copy", error.exception.read().decode())
            self.assertFalse(any(project.iterdir()))

    def test_a_game_with_a_mod_adapter_stops_reporting_no_mod_management(self):
        """The host must not say "not supported" for a game that has one.

        FF8 had a composer and a library folder but no adapter, so the header
        told the reader mod management did not exist while the plugin's own
        Mods tab managed mods. The adapter now reaches the composer, and the
        host hands it the library root the reader actually configured.
        """
        from core.desktop_host import HostApi
        from plugins.ff8.plugin import PLUGIN
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            library = root / "library"
            project = root / "project"
            (project / "direct").mkdir(parents=True)
            mod = library / "ff8" / "My Mod"
            (mod / "direct").mkdir(parents=True)
            (mod / "mod.json").write_text('{"id": "my-mod", "name": "My Mod"}', encoding="utf-8")
            host = HostApi.__new__(HostApi)
            host._mod_library_lock = threading.RLock()
            host._managed_mod_results = {}
            host._plugins = {"ff8": PLUGIN}
            host._projects = SimpleNamespace(snapshot=lambda plugin: {
                "current": str(project),
                "projects": [{"path": str(project), "current": True}]})
            host._installations = SimpleNamespace(
                snapshot=lambda plugin: {"root": str(root / "game")})
            host._settings = SimpleNamespace(
                path=root / "settings.json",
                snapshot=lambda: {"modLibraryPath": str(library)})
            host._github = SimpleNamespace(visible_repository=lambda repository: False)
            host.mod_library_location = lambda: {"root": str(library), "move": None}
            status = host.mod_library_status("ff8")
            self.assertTrue(status["canManage"], status)
            self.assertNotIn("not supported", status["message"], status)
            self.assertEqual(status["packageTypes"], ["folder", "zip"], status)
            entries = host.mod_library_entries("ff8")
            self.assertEqual([row["name"] for row in entries["entries"]], ["My Mod"], entries)
            # The adapter was given the library the host knows, not its default.
            self.assertEqual(PLUGIN.mod_adapter.context["libraryRoot"], str(library / "ff8"))
            self.assertEqual(PLUGIN.mod_adapter.context["projectRoot"], str(project))

    def test_managed_recovery_finishes_interrupted_commit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "Managed"
            target.mkdir()
            (target / "file.pak").write_bytes(b"new")
            state = root / "state.json"
            state.write_text(json.dumps({"files": {"file.pak": hashlib.sha256(b"old").hexdigest()}}))
            expected = {"files": {"file.pak": hashlib.sha256(b"new").hexdigest()}, "version": "2"}
            state.with_suffix(".tmp").write_text(json.dumps(expected))
            recover_update(target, state)
            self.assertEqual(json.loads(state.read_text()), expected)
            self.assertFalse(state.with_suffix(".tmp").exists())

    def test_managed_author_skips_network(self):
        with patch("core.managed_mods.check_release") as check:
            result = update_mod(ModLibrary(Path("unused")), "ff7r", PakModAdapter(),
                ManagedModSpec("owner/repo", "mod.zip"), Path("unused-state"), author=True)
            self.assertFalse(result["updated"])
            check.assert_not_called()

    @patch("plugins.ff7r.mod_support.list_pak", return_value=["End/Content/Test.uasset"])
    def test_managed_updates_and_failed_download(self, reader):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            library = ModLibrary(root / "library")
            state_path = root / "state.json"
            policy = ManagedModSpec("owner/repo", "mod.zip")
            def install(version, corrupt=False):
                buffer = io.BytesIO()
                with zipfile.ZipFile(buffer, "w") as archive:
                    archive.writestr("test.pak", version)
                payload = buffer.getvalue()
                release = {"tag": version, "asset": {"id": version, "size": len(payload),
                    "digest": "sha256:" + hashlib.sha256(payload).hexdigest(),
                    "browser_download_url": "https://github.com/owner/repo/releases/download/v/mod.zip"}}
                with patch("core.managed_mods.check_release", return_value=release), patch(
                        "core.managed_mods.release_request", return_value=io.BytesIO(payload[:-1] if corrupt else payload)):
                    return update_mod(library, "ff7r", PakModAdapter(), policy, state_path, author=False)
            first = install("1")
            target = Path(first["path"])
            self.assertEqual((target / "test.pak").read_text(), "1")
            with self.assertRaises(ValueError):
                install("2", corrupt=True)
            self.assertEqual((target / "test.pak").read_text(), "1")
            install("2")
            self.assertEqual((target / "test.pak").read_text(), "2")
            install("3")
            self.assertEqual((target / "test.pak").read_text(), "3")
            (target / "test.pak").write_text("User edit")
            with self.assertRaises(ValueError):
                install("4")
            self.assertEqual((target / "test.pak").read_text(), "User edit")

    @patch("plugins.ff7r.mod_support.list_pak", return_value=["End/Content/Test.uasset"])
    def test_editable_copy_failure_leaves_no_target(self, reader):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            (source / "test.pak").write_bytes(b"fixture")
            library = ModLibrary(root / "library")
            with patch("plugins.ff7r.mod_support.get_file", side_effect=OSError("bad package")):
                with self.assertRaises(OSError):
                    library.import_mod("ff7r", source, PakModAdapter(), "Copy", prepare_editable=True)
            self.assertFalse((root / "library/ff7r/Copy").exists())
            self.assertEqual((source / "test.pak").read_bytes(), b"fixture")

    def test_windows_paths(self):
        for name in ("../escape", "C:/escape", "a:stream", "NUL", "a/../b", "a. ", "a//b"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                relative_path(name)

    def test_zip_traversal_and_aliases(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "bad.zip"
            for names in (("../escape",), ("A.pak", "a.pak")):
                with zipfile.ZipFile(source, "w") as archive:
                    for name in names:
                        archive.writestr(name, "bad")
                with self.assertRaises(ValueError), package_root(source):
                    pass
            self.assertFalse((Path(temp).parent / "escape").exists())

    @patch("plugins.ff7r.mod_support.list_pak", return_value=["End/Content/Test.uasset"])
    def test_import_manual_root_and_metadata(self, reader):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "mod.zip"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("Wrapper/Mods/example_P.pak", b"fixture")
                output.writestr("Wrapper/Mods/mod.json", json.dumps({"name": "Original", "version": "1.2", "author": "Fixture"}))
            library = ModLibrary(root / "library")
            adapter = PakModAdapter()
            report = library.inspect(archive, adapter, "Wrapper/Mods")
            self.assertTrue(report["valid"])
            target = library.import_mod("ff7r", archive, adapter, "Copy", "Wrapper/Mods")
            self.assertEqual((target / "example_P.pak").read_bytes(), b"fixture")
            info = json.loads((target / "mod.json").read_text())
            self.assertEqual(info, {"name": "Copy", "version": "1.2", "author": "Fixture"})
            with self.assertRaises(FileExistsError):
                library.import_mod("ff7r", archive, adapter, "Copy", "Wrapper/Mods")

    @patch("plugins.ff7r.mod_support.list_pak", return_value=["OtherGame/Content/Test.uasset"])
    def test_invalid_content_and_runtime_package(self, reader):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "wrong.pak").write_bytes(b"fixture")
            (root / "dxgi.dll").write_bytes(b"fixture")
            report = PakModAdapter().inspect(root, [Path("wrong.pak"), Path("dxgi.dll")])
            self.assertFalse(report["valid"])
            self.assertEqual(len(report["problems"]), 2)

    def test_known_folder(self):
        if sys.platform == "win32":
            self.assertTrue(documents_folder().is_absolute())

    def test_real_pak(self):
        from plugins.ff7r.tooling import repak_path, pack_directory
        if not repak_path().is_file():
            self.skipTest("Pinned repak helper is unavailable")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source/End/Content/Fixture"
            source.mkdir(parents=True)
            (source / "test.txt").write_text("Lexeditor import fixture", encoding="utf-8")
            package = root / "package"
            package.mkdir()
            pack_directory(root / "source", package / "Fixture_P.pak", version="V4")
            report = PakModAdapter().inspect(package, [Path("Fixture_P.pak")])
            self.assertTrue(report["valid"], report)

    def test_real_editable_copy_activation(self):
        from plugins.ff7r.tooling import repak_path, pack_directory, get_file
        if not repak_path().is_file():
            self.skipTest("Pinned repak helper is unavailable")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = root / "original/End/Content/Fixture"
            original.mkdir(parents=True)
            (original / "test.txt").write_bytes(b"before")
            package = root / "package"
            package.mkdir()
            pack_directory(root / "original", package / "Original_P.pak", version="V4")
            adapter = PakModAdapter()
            copied = ModLibrary(root / "library").import_mod("ff7r", package, adapter, "Copy", prepare_editable=True)
            (copied / "content/End/Content/Fixture/test.txt").write_bytes(b"after")
            exe = root / "game/End/Binaries/Win64/ff7remake_.exe"
            exe.parent.mkdir(parents=True)
            exe.write_bytes(b"fixture")
            plan = adapter.activate([copied], root / "game")
            deployed = Path(plan["destination"]) / "Copy_P.pak"
            self.assertEqual(get_file(deployed, "End/Content/Fixture/test.txt"), b"after")
            self.assertEqual(plan["mods"], [str(copied)])

    def test_relocation_commit_and_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "old"
            source.mkdir()
            (source / "mod.json").write_text('{"name":"Keep"}')
            committed = []
            result = ModLibrary(source).relocate(root / "new", committed.append)
            self.assertEqual(committed, [root / "new"])
            self.assertTrue((source / "mod.json").exists())
            self.assertEqual((root / "new/mod.json").read_bytes(), (source / "mod.json").read_bytes())
            def fail(path):
                raise OSError("settings failure")
            with self.assertRaises(OSError):
                ModLibrary(source).relocate(root / "retry", fail)
            self.assertTrue((source / "mod.json").exists())

    def test_move_journal_recovery_and_safe_cleanup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "old"
            source.mkdir()
            (source / "keep.txt").write_text("original")
            records = []
            def fail(path):
                raise OSError("interrupted settings commit")
            with self.assertRaises(OSError):
                ModLibrary(source).relocate(root / "new", fail, journal=lambda record: records.append(dict(record)))
            self.assertEqual(records[-1]["phase"], "copied")
            commits = []
            recovered = ModLibrary.recover_move(records[-1], commits.append)
            self.assertEqual(commits, [root / "new"])
            (source / "new-user-file.txt").write_text("keep this")
            with self.assertRaises(ValueError):
                ModLibrary.remove_move_recovery(recovered, root / "new")
            self.assertTrue((source / "keep.txt").exists())
            (source / "new-user-file.txt").unlink()
            ModLibrary.remove_move_recovery(recovered, root / "new")
            self.assertFalse(source.exists())
            self.assertEqual((root / "new/keep.txt").read_text(), "original")

    @patch("plugins.ff7r.mod_support.list_pak", return_value=["End/Content/Test.uasset"])
    def test_activation_disable_and_external_edit(self, reader):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            game = root / "game"
            exe = game / "End/Binaries/Win64/ff7remake_.exe"
            exe.parent.mkdir(parents=True)
            exe.write_bytes(b"fixture")
            mod = root / "mod"
            mod.mkdir()
            (mod / "test_P.pak").write_bytes(b"fixture")
            adapter = PakModAdapter()
            report = adapter.activate([mod], game)
            deployed = Path(report["destination"]) / "test_P.pak"
            self.assertEqual(deployed.read_bytes(), b"fixture")
            deployed.write_bytes(b"external edit")
            with self.assertRaises(ValueError):
                adapter.activate([], game)
            self.assertEqual(deployed.read_bytes(), b"external edit")
            deployed.write_bytes(b"fixture")
            adapter.activate([], game)
            self.assertFalse(deployed.exists())

    @patch("plugins.ff7r.mod_support.list_pak", return_value=["End/Content/Test.uasset"])
    def test_activation_recovers_interrupted_swap(self, reader):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            game = root / "game"
            exe = game / "End/Binaries/Win64/ff7remake_.exe"
            exe.parent.mkdir(parents=True)
            exe.write_bytes(b"fixture")
            mod = root / "mod"
            mod.mkdir()
            (mod / "test.pak").write_bytes(b"before")
            adapter = PakModAdapter()
            plan = adapter.activate([mod], game)
            destination = Path(plan["destination"])
            backup = destination.with_name(".LexeditorLibrary-recovery")
            destination.rename(backup)
            adapter.recover(game)
            self.assertEqual((destination / "test.pak").read_bytes(), b"before")
            self.assertFalse(backup.exists())

    @patch("plugins.ff7r.mod_support.list_pak", return_value=["End/Content/Test.uasset"])
    def test_conflict_refuses_deployment(self, reader):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            exe = root / "game/End/Binaries/Win64/ff7remake_.exe"
            exe.parent.mkdir(parents=True)
            exe.write_bytes(b"fixture")
            mods = []
            for name in ("one", "two"):
                mod = root / name
                mod.mkdir()
                (mod / (name + ".pak")).write_bytes(b"fixture")
                mods.append(mod)
            with self.assertRaises(ValueError):
                PakModAdapter().activate(mods, root / "game")
            self.assertFalse((root / "game/End/Content/Paks/~mods").exists())


if __name__ == "__main__":
    unittest.main()
