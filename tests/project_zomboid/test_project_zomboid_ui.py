from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
EDITOR = ROOT / "plugins" / "project_zomboid" / "editor.html"
EDITOR_JS = ROOT / "plugins" / "project_zomboid" / "editor.js"
EDITOR_CSS = ROOT / "plugins" / "project_zomboid" / "editor.css"
SERVER = ROOT / "plugins" / "project_zomboid" / "server.py"

def editor_script() -> str:
    return EDITOR_JS.read_text(encoding="utf-8")


class ProjectZomboidUiContractTests(unittest.TestCase):
    def test_editor_html_is_markup_only_and_loads_relative_modules(self):
        html = EDITOR.read_text(encoding="utf-8")
        self.assertIn('href="editor.css"', html)
        self.assertIn('src="editor.js"', html)
        self.assertIn('src="/shared/framework.js"', html)
        whole_ui = html + "\n" + editor_script()
        self.assertIn("modLoaderSection(", whole_ui)
        for field in ("loader:", "output:", "order:", "safety:", "removal:"):
            self.assertIn(field, whole_ui)
        self.assertNotIn("<style", html)
        self.assertNotRegex(html, r"<script(?:\s[^>]*)?>\s*[^<\s]")
        css = EDITOR_CSS.read_text(encoding="utf-8")
        self.assertLessEqual(len(css.splitlines()), 12)
        self.assertNotRegex(css, r"\.lex-[a-z0-9-]+")

    def test_service_uses_shared_page_module_handler(self):
        source = SERVER.read_text(encoding="utf-8")
        self.assertIn("from core.plugin_http import PluginRequestHandler", source)
        self.assertIn("class Handler(PluginRequestHandler):", source)
        self.assertIn("self.send_page_module(PLUGIN_ROOT, path)", source)
        self.assertNotIn("def send_page_module(", source)
        self.assertNotIn("BaseHTTPRequestHandler", source)

    def test_editor_exposes_every_structured_script_adapter(self):
        text = editor_script()
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
        text = editor_script()
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
        text = editor_script()
        self.assertIn("LexeditorUI.pagedListDetail({", text)
        self.assertIn("LexeditorUI.columnList({", text)
        self.assertIn("LexeditorUI.detailPanel({", text)
        self.assertIn("LexeditorUI.infoHelp(", text)
        self.assertIn('type:"checkbox"', text)
        self.assertIn("edit:(row,value)=>setDraftValue", text)
        self.assertIn("editor:(row,commit)=>cellEditor", text)
        self.assertIn('width:"minmax(9rem,1.5fr)"', text)
        self.assertIn('keepMeshAnimations:{label:"Keep Anims",width:"8rem"}', text)
        self.assertIn('maxInstancesPerEmitter:{label:"Max Instances",width:"minmax(9rem,1fr)"}', text)
        self.assertNotIn('{key:"module",label:"Module",sortable:true,help:"ZedScript module containing the record."}', text)
        self.assertNotIn('class="split"', text)

    def test_metadata_scripts_and_info_use_shared_surfaces(self):
        text = editor_script()
        self.assertIn('className:"pz-metadata"', text)
        self.assertIn('className:"pz-script-layout"', text)
        self.assertIn('label:"Search Build 42 script records"', text)
        self.assertNotIn("<table>", text)
        self.assertNotIn('class="notice"', text)
        self.assertIn("dirtyCount,", text)
        self.assertIn("save:saveAllChanges", text)
        self.assertIn("discard:discardChanges", text)
        self.assertIn("emptyDetail:", text)
        self.assertIn("renderLoading(", text)
        self.assertIn("pz-error-message", text)
        self.assertIn('{id:"animationmeshes",label:"Anims"}', text)
        self.assertIn('["Animation Meshes","animationmeshes"]', text)

    def test_animation_mesh_ui_exposes_only_single_value_typed_fields(self):
        text = editor_script()
        for field_name in ("keepMeshAnimations", "meshFile", "postProcess"):
            with self.subTest(field=field_name):
                self.assertIn(f'"{field_name}"', text)
        self.assertIn("animationDirectoryCount", text)
        self.assertIn("animationPrefixCount", text)
        self.assertIn("Repeated animation source lists are preserved", text)

    def test_craft_recipe_ui_exposes_schema_typed_skill_fields(self):
        text = editor_script()
        for field_name in ("AutoLearnAll", "AutoLearnAny", "SkillRequired", "Tooltip"):
            with self.subTest(field=field_name):
                self.assertIn(f'"{field_name}"', text)
        self.assertIn("Skill:level;Skill:level", text)

    def test_deployment_renders_shared_mod_loader_section(self):
        text = editor_script()
        self.assertIn("LexeditorUI.modLoaderSection(", text)
        self.assertIn('loader:"Project Zomboid native Build 42 mod system."', text)
        self.assertIn('removal:"Remove the owned local deployment; the authoring project is preserved."', text)


if __name__ == "__main__":
    unittest.main()
