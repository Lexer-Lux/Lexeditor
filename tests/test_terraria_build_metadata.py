from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from games.terraria.build_metadata import parse_build_text, update_build_text
from games.terraria import plugin as terraria_plugin
from games.terraria import server
from project_manager import ProjectManager


class TerrariaBuildMetadataTests(unittest.TestCase):
    def test_reads_known_values_and_reports_duplicate_keys(self):
        text = (
            "author = First\n"
            "futureThing = keep me\n"
            "side = Client\n"
            "author = Second\n"
        )
        metadata = parse_build_text(text)
        self.assertEqual(metadata.values["author"], "Second")
        self.assertEqual(metadata.values["side"], "Client")
        self.assertEqual(metadata.duplicates, ("author",))
        self.assertNotIn("futureThing", metadata.values)

    def test_reads_tmodloader_list_properties(self):
        metadata = parse_build_text(
            "modReferences = MagicStorage@0.6.0, RecipeBrowser, , BossChecklist\n"
            "weakReferences = Census\n"
            "dllReferences = NativeLibrary\n"
            "sortAfter = MagicStorage, RecipeBrowser\n"
            "sortBefore = BossChecklist\n"
            "buildIgnore = obj/*, bin/*\n"
        )
        self.assertEqual(
            metadata.values["modReferences"],
            ["MagicStorage@0.6.0", "RecipeBrowser", "BossChecklist"],
        )
        self.assertEqual(metadata.values["weakReferences"], ["Census"])
        self.assertEqual(metadata.values["dllReferences"], ["NativeLibrary"])
        self.assertEqual(metadata.values["sortAfter"], ["MagicStorage", "RecipeBrowser"])
        self.assertEqual(metadata.values["sortBefore"], ["BossChecklist"])
        self.assertEqual(metadata.values["buildIgnore"], ["obj/*", "bin/*"])

    def test_noop_is_byte_exact(self):
        text = "displayName   =   Example Mod  \r\nfuture = untouched\r\n"
        self.assertEqual(update_build_text(text, {"displayName": "Example Mod"}), text)

    def test_list_semantic_noop_is_byte_exact(self):
        text = "modReferences=One,Two\r\nfuture = untouched\r\n"
        self.assertEqual(
            update_build_text(text, {"modReferences": ["One", "Two"]}),
            text,
        )

    def test_changed_write_preserves_unknown_lines_and_spacing(self):
        text = (
            "# retained future/comment-ish line\n"
            "displayName   =   Example Mod  \n"
            "futureKey = opaque=value\n"
            "side = Both\n"
        )
        changed = update_build_text(text, {"displayName": "Renamed", "side": "nosync"})
        self.assertEqual(
            changed,
            "# retained future/comment-ish line\n"
            "displayName   =   Renamed  \n"
            "futureKey = opaque=value\n"
            "side = NoSync\n",
        )

    def test_list_write_and_clear_preserve_unrelated_content(self):
        text = (
            "modReferences = One, Two\n"
            "futureKey = keep\n"
            "sortAfter = Old\n"
        )
        changed = update_build_text(
            text,
            {
                "modReferences": ["One@1.2", "Three"],
                "sortAfter": [],
                "buildIgnore": ["obj/*", "bin/*"],
            },
        )
        self.assertEqual(
            changed,
            "modReferences = One@1.2, Three\n"
            "futureKey = keep\n"
            "buildIgnore = obj/*, bin/*\n",
        )

    def test_missing_key_appends_without_rewriting_existing_content(self):
        text = "author = Lexer\r\nunknown = preserve"
        changed = update_build_text(text, {"version": "1.2.3"})
        self.assertEqual(changed, "author = Lexer\r\nunknown = preserve\r\nversion = 1.2.3\r\n")

    def test_duplicate_key_refuses_all_structured_writes(self):
        text = "author = One\nauthor = Two\nside = Both\n"
        with self.assertRaisesRegex(ValueError, "duplicate"):
            update_build_text(text, {"side": "Server"})

    def test_boolean_and_side_validation(self):
        self.assertEqual(update_build_text("", {"hideCode": True}), "hideCode = true\n")
        with self.assertRaisesRegex(ValueError, "true or false"):
            update_build_text("", {"hideCode": "yes"})
        with self.assertRaisesRegex(ValueError, "Both, Client, Server, NoSync"):
            update_build_text("", {"side": "Maybe"})

    def test_system_version_shape_is_bounded(self):
        self.assertEqual(update_build_text("", {"version": "1.2.3.4"}), "version = 1.2.3.4\n")
        for invalid in ("1", "1.2.3.4.5", "1.-2", "1.beta", "2147483648.0"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    update_build_text("", {"version": invalid})

    def test_reference_list_validation_matches_tmodloader_constraints(self):
        with self.assertRaisesRegex(ValueError, "2 to 4"):
            update_build_text("", {"modReferences": ["ExampleMod@1"]})
        with self.assertRaisesRegex(ValueError, "Duplicate mod/weak reference"):
            update_build_text(
                "",
                {"modReferences": ["ExampleMod"], "weakReferences": ["ExampleMod@1.2"]},
            )
        with self.assertRaisesRegex(ValueError, "dllReferences"):
            update_build_text(
                "",
                {"modReferences": ["ExampleMod"], "dllReferences": ["ExampleMod"]},
            )
        with self.assertRaisesRegex(ValueError, "must be a list"):
            update_build_text("", {"modReferences": "ExampleMod"})

    def test_multiline_and_unknown_structured_fields_are_rejected(self):
        with self.assertRaises(ValueError):
            update_build_text("", {"author": "one\ntwo"})
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            update_build_text("", {"futureStructured": "ExampleMod"})

    def test_shared_project_creation_renders_and_validates_tmodloader_name(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            parent = base / "ModSources"
            parent.mkdir()
            manager = ProjectManager(
                {"terraria": terraria_plugin.PLUGIN},
                path=base / "projects.json",
            )

            state = manager.create("terraria", str(parent), "Example_Mod")
            root = (parent / "Example_Mod").resolve()
            self.assertEqual(Path(state["current"]), root)
            self.assertTrue((root / "Example_Mod.csproj").is_file())
            self.assertTrue((root / "Example_Mod.cs").is_file())
            self.assertFalse((root / "LexeditorTerrariaMod.csproj").exists())
            self.assertFalse((root / "LexeditorTerrariaMod.cs").exists())

            rendered = "\n".join(
                (root / name).read_text(encoding="utf-8")
                for name in ("build.txt", "Example_Mod.csproj", "Example_Mod.cs")
            )
            self.assertNotIn("__LEXEDITOR_", rendered)
            self.assertIn("displayName = Example_Mod", rendered)
            self.assertIn("<AssemblyName>Example_Mod</AssemblyName>", rendered)
            self.assertIn("namespace Example_Mod;", rendered)

            for invalid in ("Bad Mod", "123Mod", "class", "Mod", "ModLoader", "tModLoader"):
                with self.subTest(invalid=invalid):
                    with self.assertRaises(ValueError):
                        manager.create("terraria", str(parent), invalid)
                    self.assertFalse((parent / invalid).exists())

            with self.assertRaises(ValueError):
                manager.rename("terraria", str(root), "Bad Mod")
            self.assertTrue(root.is_dir())

    def test_service_preserves_bom_and_refuses_stale_writes(self):
        previous = os.environ.get("LEXEDITOR_TERRARIA_PROJECT")
        try:
            with tempfile.TemporaryDirectory() as directory:
                os.environ["LEXEDITOR_TERRARIA_PROJECT"] = directory
                target = Path(directory) / "build.txt"
                original = server.UTF8_BOM + b"author = Lexer\r\nunknown = preserve\r\n"
                target.write_bytes(original)
                original_sha = sha256(original).hexdigest()

                state = server.save_build({"author": "Changed"}, original_sha)
                saved = target.read_bytes()
                self.assertTrue(saved.startswith(server.UTF8_BOM))
                self.assertIn(b"author = Changed\r\n", saved)
                self.assertIn(b"unknown = preserve\r\n", saved)
                self.assertEqual(state["sha256"], sha256(saved).hexdigest())

                with self.assertRaisesRegex(ValueError, "changed outside Lexeditor"):
                    server.save_build({"author": "Again"}, original_sha)
        finally:
            if previous is None:
                os.environ.pop("LEXEDITOR_TERRARIA_PROJECT", None)
            else:
                os.environ["LEXEDITOR_TERRARIA_PROJECT"] = previous

    def test_native_build_handoff_uses_tmodloader_bootstrap_and_custom_save_root(self):
        previous_project = os.environ.get("LEXEDITOR_TERRARIA_PROJECT")
        previous_install = os.environ.get("LEXEDITOR_TERRARIA_ROOT")
        previous_save_root = server.TMODLOADER_SAVE_ROOT
        try:
            with tempfile.TemporaryDirectory() as directory:
                base = Path(directory)
                install = base / "tModLoader"
                launch_utils = install / "LaunchUtils"
                launch_utils.mkdir(parents=True)
                (install / "tModLoader.dll").write_bytes(b"")
                (launch_utils / "busybox64.exe").write_bytes(b"")
                (launch_utils / "ScriptCaller.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")

                project = base / "Save Data" / "ModSources" / "ExampleMod"
                project.mkdir(parents=True)
                (project / "build.txt").write_text("displayName = Example\n", encoding="utf-8")
                (project / "ExampleMod.csproj").write_text("<Project />\n", encoding="utf-8")

                save_root = base / "Save Data"
                os.environ["LEXEDITOR_TERRARIA_PROJECT"] = str(project)
                os.environ["LEXEDITOR_TERRARIA_ROOT"] = str(install)
                server.TMODLOADER_SAVE_ROOT = save_root
                observed = {}

                def fake_run(command, **kwargs):
                    observed["command"] = command
                    observed["kwargs"] = kwargs
                    artifact = save_root / "Mods" / "ExampleMod.tmod"
                    artifact.parent.mkdir(parents=True)
                    artifact.write_bytes(b"TMOD")
                    return subprocess.CompletedProcess(command, 0, stdout="Building ExampleMod\n", stderr="")

                result = server.build_project(run_command=fake_run, platform_name="nt")
                self.assertTrue(result["ok"])
                self.assertTrue(result["artifactExists"])
                self.assertEqual(
                    observed["command"],
                    [
                        str(launch_utils / "busybox64.exe"),
                        "bash",
                        "./LaunchUtils/ScriptCaller.sh",
                        "-build",
                        str(project.resolve()),
                        "-tmlsavedirectory",
                        str(save_root.resolve()),
                    ],
                )
                self.assertEqual(observed["kwargs"]["cwd"], str(install.resolve()))
                self.assertTrue(observed["kwargs"]["capture_output"])
                self.assertFalse(observed["kwargs"]["check"])
                self.assertIn("Building ExampleMod", result["stdout"])
        finally:
            server.TMODLOADER_SAVE_ROOT = previous_save_root
            if previous_project is None:
                os.environ.pop("LEXEDITOR_TERRARIA_PROJECT", None)
            else:
                os.environ["LEXEDITOR_TERRARIA_PROJECT"] = previous_project
            if previous_install is None:
                os.environ.pop("LEXEDITOR_TERRARIA_ROOT", None)
            else:
                os.environ["LEXEDITOR_TERRARIA_ROOT"] = previous_install

    def test_native_build_status_fails_closed_without_bootstrap(self):
        previous_project = os.environ.get("LEXEDITOR_TERRARIA_PROJECT")
        previous_install = os.environ.get("LEXEDITOR_TERRARIA_ROOT")
        try:
            with tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / "ExampleMod"
                project.mkdir()
                (project / "build.txt").write_text("displayName = Example\n", encoding="utf-8")
                (project / "ExampleMod.csproj").write_text("<Project />\n", encoding="utf-8")
                os.environ["LEXEDITOR_TERRARIA_PROJECT"] = str(project)
                os.environ.pop("LEXEDITOR_TERRARIA_ROOT", None)
                state = server.build_status(platform_name="nt")
                self.assertFalse(state["available"])
                self.assertIn("not configured", state["reason"])
        finally:
            if previous_project is None:
                os.environ.pop("LEXEDITOR_TERRARIA_PROJECT", None)
            else:
                os.environ["LEXEDITOR_TERRARIA_PROJECT"] = previous_project
            if previous_install is None:
                os.environ.pop("LEXEDITOR_TERRARIA_ROOT", None)
            else:
                os.environ["LEXEDITOR_TERRARIA_ROOT"] = previous_install


if __name__ == "__main__":
    unittest.main()
