from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "games/chrono_trigger/server.py"
MAP_PREVIEWS = ROOT / "games/chrono_trigger/map_previews.js"


class DesktopMapPreviewContractTests(unittest.TestCase):
    def test_raster_endpoints_are_read_only_get_surfaces(self):
        server = SERVER.read_text(encoding="utf-8")
        post_routes = server.split("POST_ROUTES = {", 1)[1].split("}", 1)[0]
        self.assertNotIn("/api/scene-raster", post_routes)
        self.assertNotIn("/api/world-raster", post_routes)
        self.assertIn('path == "/api/scene-raster"', server)
        self.assertIn('path == "/api/world-raster"', server)
        self.assertIn("render_scene_layer", server)
        self.assertIn("render_world_layer", server)

    def test_desktop_module_is_attached_and_keeps_composition_limit_explicit(self):
        server = SERVER.read_text(encoding="utf-8")
        module = MAP_PREVIEWS.read_text(encoding="utf-8")
        self.assertIn('<script src="/map_previews.js"></script>', server)
        self.assertIn("/api/scene-raster", module)
        self.assertIn("/api/world-raster", module)
        self.assertIn("isolated layer only", module)
        self.assertIn("animated chips", module)
        self.assertIn("main/sub-screen", module)
        self.assertNotIn("/api/save/", module)

    def test_scene_view_exposes_proven_l3_raster(self):
        module = MAP_PREVIEWS.read_text(encoding="utf-8")
        self.assertIn('["raster3", "Rendered L3"]', module)
        self.assertIn('["layer3", "L3 tile IDs"]', module)
        self.assertIn('data.layers.layer3.enabled', module)

    def test_worlds_view_exposes_map_tab_without_claiming_l3(self):
        module = MAP_PREVIEWS.read_text(encoding="utf-8")
        world_panel = module.split("function worldMapPanel", 1)[1].split("worldsView =", 1)[0]
        self.assertIn('["map", "Map"]', module)
        self.assertIn('"Rendered L1"', world_panel)
        self.assertIn('"Rendered L2"', world_panel)
        self.assertNotIn('"Rendered L3"', world_panel)


if __name__ == "__main__":
    unittest.main()
