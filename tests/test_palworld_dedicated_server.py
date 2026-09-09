from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from games.palworld import build as package_build
from games.palworld.dedicated_server import (
    DedicatedServerChangedError,
    DedicatedServerOwnershipError,
    DedicatedServerRefreshError,
    deploy,
    enable,
    remove,
    revert_activation,
    status,
)


class PalworldDedicatedServerTests(unittest.TestCase):
    def fixture(self, root: Path, *, server_rule: bool = True, debug_mode: bool = False):
        server = root / "SteamLibrary" / "steamapps" / "common" / "PalServer"
        server.mkdir(parents=True)
        (server / "PalServer.exe").write_bytes(b"")
        project = root / "project"
        project.mkdir()
        payload = project / "Paks"
        payload.mkdir()
        (payload / "fixture.pak").write_bytes(b"pak-v1")
        rule = {"Type": "Paks", "Targets": ["./Paks/"]}
        if server_rule:
            rule["IsServer"] = True
        (project / "Info.json").write_text(json.dumps({
            "ModName": "Dedicated Fixture",
            "PackageName": "DedicatedFixture",
            "Version": "1",
            "DebugMode": debug_mode,
            "Author": "Lexer",
            "Dependencies": [],
            "Tags": ["Gameplay"],
            "InstallRule": [rule],
        }, indent=2) + "\n", encoding="utf-8")
        package_build.build(project)
        return server, project

    def test_deploys_owned_package_to_default_server_workshop_and_removes(self):
        with tempfile.TemporaryDirectory() as temp_name:
            server, project = self.fixture(Path(temp_name))
            deployed = deploy(project, server_root=server, allow_non_windows=True)
            state = deployed["deployment"]
            self.assertTrue(state["deployed"])
            self.assertTrue(state["owned"])
            self.assertTrue(state["current"])
            target = Path(state["targetPath"])
            self.assertEqual(server / "Mods" / "Workshop" / "Lexeditor-DedicatedFixture", target)
            self.assertEqual(b"pak-v1", (target / "Paks" / "fixture.pak").read_bytes())
            self.assertFalse((target / ".lexeditor-palworld-dedicated-deploy.json").exists())

            removed = remove(project, server_root=server, allow_non_windows=True)
            self.assertFalse(removed["deployment"]["deployed"])
            self.assertFalse(target.exists())
            self.assertTrue((project / "Info.json").is_file())

    def test_server_rule_is_required(self):
        with tempfile.TemporaryDirectory() as temp_name:
            server, project = self.fixture(Path(temp_name), server_rule=False)
            with self.assertRaisesRegex(RuntimeError, "IsServer"):
                deploy(project, server_root=server, allow_non_windows=True)
            self.assertFalse((server / "Mods" / "Workshop").exists())

    def test_external_package_change_blocks_update_and_removal(self):
        with tempfile.TemporaryDirectory() as temp_name:
            server, project = self.fixture(Path(temp_name))
            deployed = deploy(project, server_root=server, allow_non_windows=True)
            target = Path(deployed["deployment"]["targetPath"])
            (target / "external.txt").write_text("external", encoding="utf-8")
            with self.assertRaises(DedicatedServerChangedError):
                deploy(project, server_root=server, allow_non_windows=True)
            with self.assertRaises(DedicatedServerChangedError):
                remove(project, server_root=server, allow_non_windows=True)
            self.assertTrue((target / "external.txt").is_file())

    def test_same_version_changed_package_requires_debug_or_version_change(self):
        with tempfile.TemporaryDirectory() as temp_name:
            server, project = self.fixture(Path(temp_name), debug_mode=False)
            deploy(project, server_root=server, allow_non_windows=True)
            (project / "Paks" / "fixture.pak").write_bytes(b"pak-v2")
            package_build.build(project)
            with self.assertRaises(DedicatedServerRefreshError):
                deploy(project, server_root=server, allow_non_windows=True)

            info_path = project / "Info.json"
            info = json.loads(info_path.read_text("utf-8"))
            info["Version"] = "2"
            info_path.write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
            package_build.build(project)
            updated = deploy(project, server_root=server, allow_non_windows=True)
            self.assertTrue(updated["deployment"]["current"])
            self.assertEqual("2", updated["deployment"]["deployedVersion"])

    def test_activation_is_exact_byte_reversible_and_preserves_other_mods(self):
        with tempfile.TemporaryDirectory() as temp_name:
            server, project = self.fixture(Path(temp_name))
            deploy(project, server_root=server, allow_non_windows=True)
            settings = server / "Mods" / "PalModSettings.ini"
            original = (
                b"\xef\xbb\xbf[PalModSettings]\r\n"
                b"; preserve comment\r\n"
                b"bGlobalEnableMod=False\r\n"
                b"ActiveModList=OtherMod\r\n"
                b"\r\n[Other]\r\nValue=Keep\r\n"
            )
            settings.write_bytes(original)

            enabled = enable(project, server_root=server, allow_non_windows=True)
            loader = enabled["loader"]
            self.assertTrue(loader["activationOwned"])
            self.assertTrue(loader["active"])
            changed = settings.read_bytes()
            self.assertIn(b"ActiveModList=OtherMod", changed)
            self.assertIn(b"ActiveModList=DedicatedFixture", changed)
            self.assertIn(b"; preserve comment", changed)
            self.assertIn(b"[Other]\r\nValue=Keep", changed)

            restored = revert_activation(project, server_root=server, allow_non_windows=True)
            self.assertFalse(restored["loader"]["activationOwned"])
            self.assertEqual(original, settings.read_bytes())
            removed = remove(project, server_root=server, allow_non_windows=True)
            self.assertFalse(removed["deployment"]["deployed"])

    def test_external_settings_change_blocks_activation_rollback_and_package_removal(self):
        with tempfile.TemporaryDirectory() as temp_name:
            server, project = self.fixture(Path(temp_name))
            deploy(project, server_root=server, allow_non_windows=True)
            settings = server / "Mods" / "PalModSettings.ini"
            settings.write_text(
                "[PalModSettings]\n"
                "bGlobalEnableMod=False\n"
                "ActiveModList=OtherMod\n",
                encoding="utf-8",
            )
            enable(project, server_root=server, allow_non_windows=True)
            with settings.open("a", encoding="utf-8") as stream:
                stream.write("# external change\n")
            with self.assertRaises(DedicatedServerChangedError):
                revert_activation(project, server_root=server, allow_non_windows=True)
            with self.assertRaises(DedicatedServerOwnershipError):
                remove(project, server_root=server, allow_non_windows=True)
            self.assertIn("external change", settings.read_text("utf-8"))

    def test_already_active_external_config_is_not_claimed(self):
        with tempfile.TemporaryDirectory() as temp_name:
            server, project = self.fixture(Path(temp_name))
            deploy(project, server_root=server, allow_non_windows=True)
            settings = server / "Mods" / "PalModSettings.ini"
            settings.write_text(
                "[PalModSettings]\n"
                "bGlobalEnableMod=True\n"
                "ActiveModList=DedicatedFixture\n",
                encoding="utf-8",
            )
            before = settings.read_bytes()
            enabled = enable(project, server_root=server, allow_non_windows=True)
            self.assertTrue(enabled["loader"]["active"])
            self.assertFalse(enabled["loader"]["activationOwned"])
            self.assertEqual(before, settings.read_bytes())
            with self.assertRaises(DedicatedServerOwnershipError):
                remove(project, server_root=server, allow_non_windows=True)

    def test_status_infers_sibling_palserver_from_client_root(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name) / "SteamLibrary" / "steamapps" / "common"
            client = root / "Palworld"
            client.mkdir(parents=True)
            server = root / "PalServer"
            server.mkdir()
            (server / "PalServer.exe").write_bytes(b"")
            project = Path(temp_name) / "project"
            project.mkdir()
            state = status(project, client_root=client, allow_non_windows=True)
            self.assertEqual(str(server), state["serverRoot"])
            self.assertTrue(state["serverRootReady"])
            self.assertEqual("2394010", state["serverAppId"])


if __name__ == "__main__":
    unittest.main()
