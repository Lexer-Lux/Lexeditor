from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from games.stardew_valley.acceptance import acceptance_status, begin_acceptance
from games.stardew_valley.content_pack import (
    ACCEPTANCE_MARKER, ContentPackStore, deploy, deployment_status, initialize_project, revert,
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

    def test_project_declares_supported_runtime_versions(self):
        manifest = json.loads((self.project / "manifest.json").read_text(encoding="utf-8"))
        content = json.loads((self.project / "content.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["MinimumApiVersion"], "4.4.0")
        self.assertEqual(manifest["MinimumGameVersion"], "1.6.15")
        self.assertEqual(manifest["ContentPackFor"], {
            "UniqueID": "Pathoschild.ContentPatcher",
            "MinimumVersion": "2.9.0",
        })
        self.assertEqual(content["Format"], "2.9.0")

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
        (self.project / ACCEPTANCE_MARKER).write_text('{"localOnly":true}\n', encoding="utf-8")
        status = deploy(game, self.project)
        self.assertTrue(status["managed"]); self.assertFalse(status["externallyChanged"])
        target = Path(status["target"])
        self.assertFalse((target / ACCEPTANCE_MARKER).exists())
        (target / "content.json").write_text("{}\n", encoding="utf-8")
        self.assertTrue(deployment_status(game, self.project)["externallyChanged"])
        with self.assertRaises(RuntimeError): deploy(game, self.project)
        with self.assertRaises(RuntimeError): revert(game, self.project)

    def test_installed_acceptance_requires_runtime_export_and_unchanged_xnb(self):
        game = self.root / "game"
        data = game / "Content" / "Data"; data.mkdir(parents=True)
        xnb = data / "Objects.xnb"; xnb.write_bytes(b"installed-objects")
        (game / "Stardew Valley.exe").write_bytes(b"game")
        (game / "StardewModdingAPI.exe").write_bytes(b"smapi")
        cp = game / "Mods" / "Content Patcher"; cp.mkdir(parents=True)
        (cp / "manifest.json").write_text(json.dumps({
            "Name": "Content Patcher",
            "UniqueID": "Pathoschild.ContentPatcher",
            "Version": "2.9.1",
            "MinimumApiVersion": "4.4.0",
        }) + "\n", encoding="utf-8")
        store = ContentPackStore(self.project)
        opened = store.objects()
        store.save_objects(opened["sha256"], [{"id": "390", "fields": {"Price": 77}}])
        deploy(game, self.project)
        manifest = json.loads((self.project / "manifest.json").read_text(encoding="utf-8"))
        log = self.root / "SMAPI-latest.txt"
        log.write_text("old session\n", encoding="utf-8")
        exported = game / "patch export" / "Data_Objects.json"

        with patch.dict(os.environ, {"LEXEDITOR_STARDEW_SMAPI_LOG": str(log)}):
            waiting = begin_acceptance(game, self.project)
            self.assertEqual(waiting["state"], "waiting-for-run")
            self.assertFalse(waiting["accepted"])
            self.assertTrue(waiting["objectsXnbUnchanged"])
            log.write_text(
                "[SMAPI] SMAPI 4.5.2 with Stardew Valley 1.6.15 build 24354 on Windows 11\n"
                "[SMAPI] Loaded 2 mods:\n"
                "[SMAPI]    Content Patcher 2.9.1 by Pathoschild | Loads content packs\n"
                "[SMAPI] Loaded 1 content packs:\n"
                f"[SMAPI]    {manifest['Name']} 1.0.0 by Lexer | for Content Patcher\n",
                encoding="utf-8",
            )
            no_export = acceptance_status(game, self.project)
            self.assertFalse(no_export["accepted"])
            self.assertFalse(no_export["freshObjectsExport"])
            self.assertTrue(any("patch export" in value for value in no_export["blockers"]))

            exported.parent.mkdir(parents=True)
            exported.write_text(json.dumps({"390": {"Price": 76}}) + "\n", encoding="utf-8")
            mismatch = acceptance_status(game, self.project)
            self.assertFalse(mismatch["accepted"])
            self.assertTrue(mismatch["freshObjectsExport"])
            self.assertFalse(mismatch["objectsExportMatchesExpected"])
            self.assertTrue(any("390.Price" in value for value in mismatch["objectsExportMismatches"]))

            exported.write_text(json.dumps({"390": {"Price": 77}}) + "\n", encoding="utf-8")
            accepted = acceptance_status(game, self.project)
            self.assertTrue(accepted["accepted"])
            self.assertEqual(accepted["smapiVersion"], "4.5.2")
            self.assertEqual(accepted["gameVersion"], "1.6.15")
            self.assertTrue(accepted["platformMatchesTarget"])
            self.assertTrue(accepted["contentPatcherSeen"])
            self.assertTrue(accepted["contentPatcherVersionMatches"])
            self.assertTrue(accepted["smapiMeetsContentPatcherMinimum"])
            self.assertTrue(accepted["projectMentioned"])
            self.assertTrue(accepted["projectLoaded"])
            self.assertTrue(accepted["objectsExportMatchesExpected"])
            self.assertTrue(accepted["objectsXnbUnchanged"])

            xnb.write_bytes(b"mutated-installed-objects")
            changed = acceptance_status(game, self.project)
            self.assertFalse(changed["accepted"])
            self.assertFalse(changed["objectsXnbUnchanged"])
            self.assertTrue(any("Objects.xnb changed" in value for value in changed["blockers"]))

            xnb.write_bytes(b"installed-objects")
            reopened = store.objects()
            store.save_objects(reopened["sha256"], [{"id": "390", "fields": {"Price": 78}}])
            deploy(game, self.project)
            stale = acceptance_status(game, self.project)
            self.assertFalse(stale["accepted"])
            self.assertTrue(stale["deploymentMatchesProject"])
            self.assertFalse(stale["projectMatchesBaseline"])
            self.assertTrue(any("project changed" in value.casefold() for value in stale["blockers"]))


if __name__ == "__main__": unittest.main()
