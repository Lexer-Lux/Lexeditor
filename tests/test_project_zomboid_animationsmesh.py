from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from games.project_zomboid import animationsmesh, core


class ProjectZomboidAnimationsMeshTests(unittest.TestCase):
    def make_project(self, root: Path) -> Path:
        project = root / "mod"
        scripts = project / "42" / "media" / "scripts"
        scripts.mkdir(parents=True)
        (project / "42" / "mod.info").write_text("name=Test\nid=Test\n", encoding="utf-8")
        (scripts / "animations.txt").write_text(
            "module Base\n"
            "{\n"
            "  animationsMesh PugAnim\n"
            "  {\n"
            "    animationDirectory = media/anims_X/Pug,\n"
            "    animationDirectory = media/anims_X/Common,\n"
            "    animationPrefix = Pug_,\n"
            "    keepMeshAnimations = true,\n"
            "    meshFile = Skinned/Pug_Body,\n"
            "    postProcess = +TRIANGULATE,\n"
            "    FutureField = KeepMe,\n"
            "  }\n"
            "}\n",
            encoding="utf-8",
        )
        return project

    def test_surgical_edit_preserves_repeated_animation_sources_and_unknown_data(self):
        with tempfile.TemporaryDirectory() as name:
            root = self.make_project(Path(name))
            row = animationsmesh.read(root)["rows"][0]
            self.assertEqual(row["animationDirectoryCount"], 2)
            self.assertEqual(row["animationPrefixCount"], 1)
            self.assertEqual(row["fields"]["keepMeshAnimations"], "true")
            saved = animationsmesh.save(
                root, row["path"], row["module"], row["id"], row["sha256"],
                {
                    "keepMeshAnimations": "false",
                    "meshFile": "Skinned/Pug_Body_v2",
                    "postProcess": "+TRIANGULATE;+NORMALS",
                },
            )
            text = (root / row["path"]).read_text(encoding="utf-8")
            self.assertEqual(saved["fields"]["keepMeshAnimations"], "false")
            self.assertEqual(saved["fields"]["meshFile"], "Skinned/Pug_Body_v2")
            self.assertEqual(text.count("animationDirectory ="), 2)
            self.assertIn("animationPrefix = Pug_,", text)
            self.assertIn("FutureField = KeepMe,", text)

    def test_same_line_duplicate_editable_property_fails_closed(self):
        with tempfile.TemporaryDirectory() as name:
            root = self.make_project(Path(name))
            script = root / "42" / "media" / "scripts" / "animations.txt"
            original = script.read_text(encoding="utf-8").replace(
                "    keepMeshAnimations = true,\n",
                "    keepMeshAnimations = true, keepMeshAnimations = false,\n",
            )
            script.write_text(original, encoding="utf-8")
            row = animationsmesh.read(root)["rows"][0]
            self.assertIn("keepMeshAnimations", row["duplicateKeys"])
            with self.assertRaisesRegex(core.ProjectZomboidError, "duplicated animationsMesh properties"):
                animationsmesh.save(
                    root, row["path"], row["module"], row["id"], row["sha256"],
                    {"keepMeshAnimations": "false"},
                )
            self.assertEqual(script.read_text(encoding="utf-8"), original)

    def test_validation_missing_and_stale_write_fail_closed(self):
        with tempfile.TemporaryDirectory() as name:
            root = self.make_project(Path(name))
            row = animationsmesh.read(root)["rows"][0]
            with self.assertRaisesRegex(core.ProjectZomboidError, "true or false"):
                animationsmesh.save(
                    root, row["path"], row["module"], row["id"], row["sha256"],
                    {"keepMeshAnimations": "yes"},
                )

            script = root / row["path"]
            script.write_text(
                script.read_text(encoding="utf-8").replace("    meshFile = Skinned/Pug_Body,\n", ""),
                encoding="utf-8",
            )
            current = animationsmesh.read(root)["rows"][0]
            with self.assertRaisesRegex(core.ProjectZomboidError, "missing: meshFile"):
                animationsmesh.save(
                    root, current["path"], current["module"], current["id"], current["sha256"],
                    {"meshFile": "Skinned/Other"},
                )

            script.write_text(script.read_text(encoding="utf-8") + "// external\n", encoding="utf-8")
            with self.assertRaisesRegex(core.ProjectZomboidError, "changed outside Lexeditor"):
                animationsmesh.save(
                    root, current["path"], current["module"], current["id"], current["sha256"],
                    {"postProcess": "+NORMALS"},
                )


if __name__ == "__main__":
    unittest.main()
