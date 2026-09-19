from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
EDITOR = ROOT / "games" / "project_zomboid" / "editor.html"


class ProjectZomboidUiContractTests(unittest.TestCase):
    def test_editor_exposes_every_structured_script_adapter(self):
        text = EDITOR.read_text(encoding="utf-8")
        for tab in ("animationmeshes", "items", "evolved", "crafts", "fixing", "fluids", "vehicles", "sounds", "models", "mannequins", "timedactions"):
            with self.subTest(tab=tab):
                self.assertIn(f'id:"{tab}"', text)
        for endpoint in ("/api/animationmeshes", "/api/items", "/api/evolvedrecipes", "/api/craftrecipes", "/api/fixings", "/api/fluids", "/api/vehicles", "/api/sounds", "/api/models", "/api/mannequins", "/api/timedactions"):
            with self.subTest(endpoint=endpoint):
                self.assertIn(endpoint, text)
        for renderer, save in (
            ("renderAnimationMeshes", "/api/animationmeshes/save"),
            ("renderFixings", "/api/fixings/save"),
            ("renderVehicles", "/api/vehicles/save"),
            ("renderSounds", "/api/sounds/save"),
            ("renderModels", "/api/models/save"),
            ("renderMannequins", "/api/mannequins/save"),
            ("renderTimedActions", "/api/timedactions/save"),
        ):
            with self.subTest(renderer=renderer):
                self.assertIn(renderer, text)
                self.assertIn(save, text)

    def test_shared_shell_owns_data_map_and_info_navigation(self):
        text = EDITOR.read_text(encoding="utf-8")
        self.assertIn("LexeditorUI.mountShell({", text)
        self.assertIn('help:()=>navigate("datamap")', text)
        self.assertIn('info:()=>navigate("info")', text)
        self.assertIn("renderDatamap", text)
        self.assertIn("LexeditorUI.dataMap({", text)
        self.assertIn("open:row=>navigate(row.target)", text)
        self.assertIn("renderInfo", text)
        self.assertNotIn('data-tab="datamap"', text)
        self.assertNotIn('data-tab="deployment"', text)

    def test_structured_editors_use_shared_paged_table_and_detail_controls(self):
        text = EDITOR.read_text(encoding="utf-8")
        self.assertIn("LexeditorUI.pagedListDetail({", text)
        self.assertIn("LexeditorUI.columnList({", text)
        self.assertIn("LexeditorUI.detailPanel({", text)
        self.assertIn("LexeditorUI.infoHelp(", text)
        self.assertIn('type:"checkbox"', text)
        self.assertNotIn('class="split"', text)

    def test_animation_mesh_ui_exposes_only_single_value_typed_fields(self):
        text = EDITOR.read_text(encoding="utf-8")
        for field_name in ("keepMeshAnimations", "meshFile", "postProcess"):
            with self.subTest(field=field_name):
                self.assertIn(f'"{field_name}"', text)
        self.assertIn("animationDirectoryCount", text)
        self.assertIn("animationPrefixCount", text)
        self.assertIn("Repeated animation source lists are preserved", text)

    def test_craft_recipe_ui_exposes_schema_typed_skill_fields(self):
        text = EDITOR.read_text(encoding="utf-8")
        for field_name in ("AutoLearnAll", "AutoLearnAny", "SkillRequired", "Tooltip"):
            with self.subTest(field=field_name):
                self.assertIn(f'"{field_name}"', text)
        self.assertIn("Skill:level;Skill:level", text)

    def test_deployment_renders_shared_mod_loader_section(self):
        text = EDITOR.read_text(encoding="utf-8")
        self.assertIn("LexeditorUI.modLoaderSection(", text)
        self.assertIn('loader:"Project Zomboid native Build 42 mod system."', text)
        self.assertIn('removal:"Remove the owned local deployment; the authoring project is preserved."', text)


if __name__ == "__main__":
    unittest.main()
