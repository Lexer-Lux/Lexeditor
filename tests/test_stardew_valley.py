from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from games.stardew_valley.content_pack import (
    ContentPackStore, deploy, deployment_status, initialize_project, revert,
)
from games.stardew_valley import paths, server
from games.stardew_valley.source_data import load_base_objects, objects_source_path


class StardewContentPackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        shutil.copytree(paths.PROJECT_TEMPLATE_ROOT, self.project)
        initialize_project(self.project)

    def tearDown(self): self.temp.cleanup()

    def test_object_edit_preserves_unknown_data_and_rejects_stale_save(self):
        content = json.loads((self.project / "content.json").read_text(encoding="utf-8"))
        content["CustomRoot"] = {"keep": True}
        content["Changes"].append({"Action": "EditData", "Target": "Data/Objects", "Fields": {
            "390": {"Description": "keep me", "Price": 10}
        }})
        (self.project / "content.json").write_text(json.dumps(content, indent=2) + "\n", encoding="utf-8")
        store = ContentPackStore(self.project); opened = store.objects()
        saved = store.save_objects(opened["sha256"], [{"id": "390", "fields": {"Price": 25, "IsDrink": True}}])
        self.assertEqual(saved["rows"][0]["fields"]["Price"], 25)
        raw = json.loads((self.project / "content.json").read_text(encoding="utf-8"))
        self.assertEqual(raw["CustomRoot"], {"keep": True})
        self.assertEqual(raw["Changes"][0]["Fields"]["390"]["Description"], "keep me")
        with self.assertRaises(RuntimeError):
            store.save_objects(opened["sha256"], [{"id": "390", "fields": {"Price": 26}}])

    def test_unpacked_objects_are_read_only_and_merge_with_project_overrides(self):
        game = self.root / "game"
        source = objects_source_path(game)
        source.parent.mkdir(parents=True)
        source.write_text(json.dumps({
            "390": {
                "Name": "Stone", "DisplayName": "Stone", "Description": "A useful material.",
                "Price": 2, "Edibility": -300, "IsDrink": False,
            },
            "MossSoup": {
                "Name": "Moss Soup", "DisplayName": "Moss Soup", "Description": "It's thick.",
                "Price": 40,
            },
        }, indent=2) + "\n", encoding="utf-8")
        source_before = source.read_bytes()
        base, status = load_base_objects(game)
        self.assertTrue(status["available"]); self.assertEqual(status["recordCount"], 2)
        self.assertEqual(base["MossSoup"]["baseFields"]["Edibility"], -300)
        self.assertFalse(base["MossSoup"]["baseFields"]["IsDrink"])

        with patch.object(server.paths, "GAME_ROOT", game), patch.object(server.paths, "PROJECT_ROOT", self.project):
            opened = server.objects_dataset()
            rows = {row["id"]: row for row in opened["rows"]}
            self.assertEqual(rows["390"]["baseFields"]["Price"], 2)
            self.assertEqual(rows["390"]["fields"], {})
            ContentPackStore(self.project).save_objects(opened["sha256"], [
                {"id": "390", "fields": {"Price": 25}}
            ])
            merged = server.objects_dataset()
            rows = {row["id"]: row for row in merged["rows"]}
            self.assertEqual(rows["390"]["baseFields"]["Price"], 2)
            self.assertEqual(rows["390"]["fields"]["Price"], 25)
            self.assertTrue(rows["390"]["sourcePresent"])
            self.assertTrue(merged["baseSource"]["available"])
        self.assertEqual(source.read_bytes(), source_before)

    def test_deploy_and_revert_are_managed_and_refuse_external_changes(self):
        game = self.root / "game"; (game / "Content").mkdir(parents=True)
        (game / "Stardew Valley.exe").write_bytes(b"game")
        (game / "StardewModdingAPI.exe").write_bytes(b"smapi")
        cp = game / "Mods" / "Content Patcher"; cp.mkdir(parents=True)
        (cp / "manifest.json").write_text('{"UniqueID":"Pathoschild.ContentPatcher"}\n', encoding="utf-8")
        status = deploy(game, self.project)
        self.assertTrue(status["managed"]); self.assertFalse(status["externallyChanged"])
        target = Path(status["target"]); (target / "content.json").write_text("{}\n", encoding="utf-8")
        self.assertTrue(deployment_status(game, self.project)["externallyChanged"])
        with self.assertRaises(RuntimeError): deploy(game, self.project)
        with self.assertRaises(RuntimeError): revert(game, self.project)


if __name__ == "__main__": unittest.main()
