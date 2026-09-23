"""Synthetic FF7 -> FFNx Direct Mode deployment acceptance.

No game assets are bundled. The fixtures prove exact project/export/deploy
behavior while keeping installed source files byte-identical.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import tempfile
import unittest

from plugins.ff7 import datasets, deployment, extended
from plugins.ff7.archives import FieldArchive, WorldArchive
from plugins.ff7.battle import SceneArchive
from plugins.ff7.storage import target_path

import verify_ff7_completion as complete
import verify_ff7_datasets as kernel_fixture
import verify_ff7_extended as extra_fixture


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.game = self.root / "game"
        self.project = self.root / "project"
        self.work = self.game / "ff7" / "workingdir"
        self.sources = {}

        kernel = self.work / "data/lang-en/kernel/kernel.bin"
        kernel_fixture.write_kernel(kernel)
        self.sources["kernel"] = kernel

        values = {
            "text": (self.work / "data/lang-en/kernel/kernel2.bin", extra_fixture.text_fixture()),
            "scene": (self.work / "data/battle/scene.bin", extra_fixture.scene_fixture()),
            "field": (self.work / "data/field/flevel.lgp",
                      complete.lgp_fixture([("maplist", b"list"), ("field1", complete.field_fixture())])),
            "world": (self.work / "data/wm/world_us.lgp",
                      complete.lgp_fixture([("enc_w.bin", complete.world_fixture()), ("opaque", b"keep")])),
            "shop": (self.game / "ff7/resources/ff7_1.02/ff7_en", extra_fixture.exe_fixture()),
        }
        for key, (path, raw) in values.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            self.sources[key] = path
        self.originals = {key: path.read_bytes() for key, path in self.sources.items()}
        self.work.mkdir(parents=True, exist_ok=True)
        (self.work / "FFNx.toml").write_text(
            '# FFNx fixture\ndirect_mode_path = "direct"\nwindowed = true\n',
            encoding="utf-8",
        )

    def target(self, key):
        source = self.sources[key]
        return target_path(self.game, self.project, source, source.relative_to(self.game))

    def edit_all_direct_families(self):
        kernel = datasets.Kernel(self.sources["kernel"])
        rows = kernel.records("weapons")
        rows[0]["values"]["attackStrength"] += 1
        kernel.apply("weapons", rows)
        kernel.save(self.target("kernel"))

        text = extended.KernelText(self.sources["text"].read_bytes())
        rows = text.records("texts")
        rows[0]["values"]["text"] = "Direct deployment text"
        text.apply("texts", rows)
        self.target("text").parent.mkdir(parents=True, exist_ok=True)
        self.target("text").write_bytes(text.to_bytes())

        scene = SceneArchive(self.sources["scene"].read_bytes())
        rows = scene.records("enemies")
        rows[0]["values"]["hp"] = 12345
        scene.apply("enemies", rows)
        self.target("scene").parent.mkdir(parents=True, exist_ok=True)
        self.target("scene").write_bytes(scene.to_bytes())

        field = FieldArchive(self.sources["field"].read_bytes())
        rows = field.records()
        rows[0]["values"]["battle0"] = 222
        field.apply("fieldEncounters", rows)
        self.target("field").parent.mkdir(parents=True, exist_ok=True)
        self.target("field").write_bytes(field.to_bytes())

        world = WorldArchive(self.sources["world"].read_bytes())
        rows = world.records("worldEncounters")
        rows[0]["values"]["battle0"] = 333
        world.apply("worldEncounters", rows)
        self.target("world").parent.mkdir(parents=True, exist_ok=True)
        self.target("world").write_bytes(world.to_bytes())

    def assert_installed_unchanged(self):
        self.assertEqual({key:path.read_bytes() for key,path in self.sources.items()}, self.originals)

    def test_export_deploy_and_remove_owned_direct_files(self):
        self.edit_all_direct_families()
        plan = deployment.build_plan(self.game, self.project)
        self.assertTrue(plan["ready"], plan["blocked"])
        paths = {row["path"] for row in plan["files"]}
        self.assertTrue(any(path.startswith("kernel/kernel.bin.chunk.") for path in paths))
        self.assertIn("kernel/kernel.bin.chunk.10", paths)
        self.assertIn("battle/scene.bin.chunk.0", paths)
        self.assertIn("flevel.lgp/field1.chunk.7", paths)
        self.assertIn("world_us.lgp/enc_w.bin", paths)
        self.assertEqual(Path(plan["ffnx"]["directRoot"]).resolve(), (self.work / "direct").resolve())

        exported = deployment.export_project(self.game, self.project)
        export_root = Path(exported["exportRoot"])
        self.assertTrue((export_root / deployment.MANIFEST_NAME).is_file())
        self.assertFalse((self.work / "direct").exists())
        self.assert_installed_unchanged()

        deployed = deployment.deploy_project(self.game, self.project)
        direct = Path(deployed["directRoot"])
        for relative in paths:
            self.assertTrue((direct / relative).is_file(), relative)
        self.assertTrue((direct / deployment.MANIFEST_NAME).is_file())
        self.assert_installed_unchanged()

        removed = deployment.remove_deployment(self.game)
        self.assertEqual(removed["conflicts"], [])
        self.assertEqual(removed["removed"], len(paths))
        self.assertFalse((direct / deployment.MANIFEST_NAME).exists())
        self.assert_installed_unchanged()

    def test_unowned_collision_is_never_overwritten(self):
        self.edit_all_direct_families()
        plan = deployment.build_plan(self.game, self.project)
        relative = plan["files"][0]["path"]
        direct = Path(plan["ffnx"]["directRoot"])
        collision = direct / relative
        collision.parent.mkdir(parents=True, exist_ok=True)
        collision.write_bytes(b"another mod owns this")
        with self.assertRaisesRegex(ValueError, "already owned by another mod"):
            deployment.deploy_project(self.game, self.project)
        self.assertEqual(collision.read_bytes(), b"another mod owns this")
        self.assert_installed_unchanged()

    def test_external_change_is_left_in_place_on_remove(self):
        self.edit_all_direct_families()
        deployed = deployment.deploy_project(self.game, self.project)
        direct = Path(deployed["directRoot"])
        relative = deployed["files"][0]["path"]
        changed = direct / relative
        changed.write_bytes(b"external edit")
        result = deployment.remove_deployment(self.game)
        self.assertIn(relative, result["conflicts"])
        self.assertEqual(changed.read_bytes(), b"external edit")
        self.assertTrue((direct / deployment.MANIFEST_NAME).exists())

    def test_executable_project_edit_blocks_partial_deployment(self):
        target = self.target("shop")
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = bytearray(self.sources["shop"].read_bytes())
        raw[-1] ^= 1
        target.write_bytes(raw)
        plan = deployment.build_plan(self.game, self.project)
        self.assertFalse(plan["ready"])
        self.assertTrue(any("Executable-backed edits" in value for value in plan["blocked"]))
        with self.assertRaisesRegex(ValueError, "undeployable changes"):
            deployment.export_project(self.game, self.project)

    def test_unknown_kernel_mutation_blocks_deployment(self):
        kernel = datasets.Kernel(self.sources["kernel"])
        kernel.sections[0][2] ^= 1
        kernel.save(self.target("kernel"))
        plan = deployment.build_plan(self.game, self.project)
        self.assertFalse(plan["ready"])
        self.assertTrue(any("outside Lexeditor" in value for value in plan["blocked"]))

    def test_ffnx_path_must_stay_inside_runtime_directory(self):
        (self.work / "FFNx.toml").write_text('direct_mode_path = "../escape"\n', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "direct_mode_path"):
            deployment.build_plan(self.game, self.project)


if __name__ == "__main__":
    unittest.main(verbosity=2)
