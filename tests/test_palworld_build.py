from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest

from games.palworld.build import (
    BuildChangedError,
    BuildOwnershipError,
    build,
    revert,
    status,
)


class PalworldBuildTests(unittest.TestCase):
    def make_project(self, root: Path) -> Path:
        project = root / "project"
        project.mkdir()
        (project / "thumbnail.png").write_bytes(b"png-fixture")
        paks = project / "Paks"
        paks.mkdir()
        (paks / "Fixture.pak").write_bytes(b"pak-fixture")
        pal_raw = project / "PalSchema" / "Balance" / "raw"
        pal_raw.mkdir(parents=True)
        (pal_raw / "balance.json").write_text('{"DT_Test":{"Row":{"Value":1}}}\n', encoding="utf-8")
        (pal_raw / "balance.json.lexeditor.bak").write_text("must not ship", encoding="utf-8")
        info = {
            "ModName": "Build Fixture",
            "PackageName": "BuildFixture",
            "Thumbnail": "thumbnail.png",
            "Version": "1",
            "DebugMode": False,
            "Author": "Lexer",
            "Dependencies": ["PalSchema"],
            "Tags": ["PalSchema"],
            "InstallRule": [
                {"Type": "Paks", "Targets": ["./Paks/"]},
                {"Type": "PalSchema", "Targets": ["./PalSchema/"]},
            ],
        }
        (project / "Info.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
        return project

    def test_build_contains_only_clean_official_package_sources(self):
        with tempfile.TemporaryDirectory() as temp_name:
            project = self.make_project(Path(temp_name))
            result = build(project)
            target = Path(result["packagePath"])
            self.assertTrue(result["built"])
            self.assertTrue(result["owned"])
            self.assertTrue(result["current"])
            self.assertTrue((target / "Info.json").is_file())
            self.assertEqual(b"png-fixture", (target / "thumbnail.png").read_bytes())
            self.assertEqual(b"pak-fixture", (target / "Paks" / "Fixture.pak").read_bytes())
            self.assertTrue((target / "PalSchema" / "Balance" / "raw" / "balance.json").is_file())
            self.assertFalse((target / "PalSchema" / "Balance" / "raw" / "balance.json.lexeditor.bak").exists())
            self.assertFalse((target / ".lexeditor-palworld-build.json").exists())
            self.assertEqual(result["desiredDigest"], result["currentDigest"])

    def test_rebuild_is_noop_until_sources_change(self):
        with tempfile.TemporaryDirectory() as temp_name:
            project = self.make_project(Path(temp_name))
            first = build(project)
            target = Path(first["packagePath"])
            before = (target / "Paks" / "Fixture.pak").read_bytes()
            second = build(project)
            self.assertTrue(second["current"])
            self.assertEqual(before, (target / "Paks" / "Fixture.pak").read_bytes())

            (project / "Paks" / "Fixture.pak").write_bytes(b"changed-pak")
            stale = status(project)
            self.assertFalse(stale["current"])
            rebuilt = build(project)
            self.assertTrue(rebuilt["current"])
            self.assertEqual(b"changed-pak", (target / "Paks" / "Fixture.pak").read_bytes())

    def test_external_build_change_blocks_rebuild_and_revert(self):
        with tempfile.TemporaryDirectory() as temp_name:
            project = self.make_project(Path(temp_name))
            result = build(project)
            target = Path(result["packagePath"])
            (target / "Paks" / "Fixture.pak").write_bytes(b"external")
            with self.assertRaises(BuildChangedError):
                build(project)
            with self.assertRaises(BuildChangedError):
                revert(project)
            self.assertEqual(b"external", (target / "Paks" / "Fixture.pak").read_bytes())

    def test_unowned_build_target_is_never_overwritten_or_deleted(self):
        with tempfile.TemporaryDirectory() as temp_name:
            project = self.make_project(Path(temp_name))
            target = project / "build" / "official-package"
            target.mkdir(parents=True)
            (target / "external.txt").write_text("mine", encoding="utf-8")
            with self.assertRaises(BuildOwnershipError):
                build(project)
            with self.assertRaises(BuildOwnershipError):
                revert(project)
            self.assertEqual("mine", (target / "external.txt").read_text("utf-8"))

    def test_revert_removes_only_unchanged_owned_snapshot(self):
        with tempfile.TemporaryDirectory() as temp_name:
            project = self.make_project(Path(temp_name))
            result = build(project)
            target = Path(result["packagePath"])
            manifest = Path(result["manifestPath"])
            self.assertTrue(target.is_dir())
            self.assertTrue(manifest.is_file())
            reverted = revert(project)
            self.assertFalse(target.exists())
            self.assertFalse(manifest.exists())
            self.assertFalse(reverted["built"])

    def test_missing_declared_target_fails_without_partial_build(self):
        with tempfile.TemporaryDirectory() as temp_name:
            project = self.make_project(Path(temp_name))
            (project / "Paks" / "Fixture.pak").unlink()
            (project / "Paks").rmdir()
            with self.assertRaises(FileNotFoundError):
                build(project)
            self.assertFalse((project / "build" / "official-package").exists())

    def test_missing_thumbnail_fails(self):
        with tempfile.TemporaryDirectory() as temp_name:
            project = self.make_project(Path(temp_name))
            (project / "thumbnail.png").unlink()
            with self.assertRaises(FileNotFoundError):
                build(project)

    def test_root_target_is_refused(self):
        with tempfile.TemporaryDirectory() as temp_name:
            project = self.make_project(Path(temp_name))
            info = json.loads((project / "Info.json").read_text("utf-8"))
            info["InstallRule"] = [{"Type": "Paks", "Targets": ["./"]}]
            (project / "Info.json").write_text(json.dumps(info), encoding="utf-8")
            with self.assertRaises(ValueError):
                build(project)

    def test_symlink_content_is_refused_when_platform_allows_links(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            project = self.make_project(root)
            outside = root / "outside.bin"
            outside.write_bytes(b"outside")
            link = project / "Paks" / "link.bin"
            try:
                os.symlink(outside, link)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable on this runner")
            with self.assertRaises(RuntimeError):
                build(project)


if __name__ == "__main__":
    unittest.main()
