"""Run FF7 rendered tests with framework.css and neutral.css both inlined."""
from __future__ import annotations

import json
import unittest
import verify_ff7_rendered as target


def open_with_neutral(self, edition="ff7"):
    self.page.goto("about:blank")
    html = (target.ROOT / "games/ff7/editor.html").read_text()
    # framework.js resolves optional shared assets relative to document.baseURI.
    # Synthetic set_content() pages otherwise use the non-hierarchical about:blank URL.
    html = html.replace("<head>", '<head><base href="http://127.0.0.1:9/">', 1)
    shared_css = (target.ROOT / "ui/framework.css").read_text() + "\n" + (target.ROOT / "ui/neutral.css").read_text()
    html = html.replace('<link rel="stylesheet" href="/shared/framework.css">', "<style>" + shared_css + "</style>")
    html = html.replace('<link rel="stylesheet" href="/shared/neutral.css">', "")
    code = target.HOST + "\nwindow.__lexeditorPlugin=" + json.dumps({"id":edition,"name":"FF7 fixture","edition":edition}) + ";\n" + (target.ROOT / "ui/framework.js").read_text()
    html = html.replace('<script src="/shared/framework.js"></script>', "<script>" + code + "</script>")
    self.page.set_content(html, wait_until="domcontentloaded")
    self.page.wait_for_function("state.loaded === true")
    self.assertEqual(self.errors, [])


def test_accessory_description_is_editable_game_text(self):
    self.install()
    self.open()
    self.navigate("accessories")
    description = self.page.get_by_label("Description for Record0", exact=True)
    self.assertTrue(description.is_editable())
    self.assertEqual(description.input_value(), "Help0")
    heading = self.page.locator(".ff7-detail .lex-detail-panel-heading").first.inner_text()
    self.assertNotIn("ff7", heading.casefold())
    description.fill("Edited accessory description")
    self.save()
    status, data = self.backend.request("/api/data")
    self.assertEqual(status, 200)
    self.assertEqual(data["records"]["accessories"][0]["description"], "Edited accessory description")

    self.navigate("characters")
    self.assertEqual(self.page.get_by_label("Description for Slot0", exact=True).count(), 0)
    self.assertNotIn("Initial stats, equipment, materia/AP", self.page.locator("main").inner_text())
    self.originals_unchanged()


target.RenderedTests.open = open_with_neutral
target.RenderedTests.test_accessory_description_is_editable_game_text = test_accessory_description_is_editable_game_text

if __name__ == "__main__":
    unittest.main(module=target, verbosity=2)
