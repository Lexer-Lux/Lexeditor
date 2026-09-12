from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
EDITOR = ROOT / "games" / "project_zomboid" / "editor.html"


class ProjectZomboidUiContractTests(unittest.TestCase):
    def test_editor_exposes_every_structured_script_adapter(self):
        text = EDITOR.read_text(encoding="utf-8")
        for tab in ("items", "evolved", "crafts", "fluids", "vehicles", "sounds"):
            with self.subTest(tab=tab):
                self.assertIn(f'data-tab="{tab}"', text)
        for endpoint in ("/api/items", "/api/evolvedrecipes", "/api/craftrecipes", "/api/fluids", "/api/vehicles", "/api/sounds"):
            with self.subTest(endpoint=endpoint):
                self.assertIn(endpoint, text)
        self.assertIn("renderVehicles", text)
        self.assertIn("/api/vehicles/save", text)
        self.assertIn("renderSounds", text)
        self.assertIn("/api/sounds/save", text)

    def test_deployment_renders_shared_mod_loader_section(self):
        text = EDITOR.read_text(encoding="utf-8")
        self.assertIn("LexeditorUI.modLoaderSection(", text)
        self.assertIn('loader:"Project Zomboid native Build 42 mod system."', text)
        self.assertIn('removal:"Remove the owned local deployment; the authoring project is preserved."', text)


if __name__ == "__main__":
    unittest.main()
