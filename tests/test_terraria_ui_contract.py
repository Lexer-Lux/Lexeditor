from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "games" / "terraria" / "editor.html"
JS = ROOT / "games" / "terraria" / "editor.js"
CSS = ROOT / "games" / "terraria" / "editor.css"
SERVER = ROOT / "games" / "terraria" / "server.py"


class TerrariaUiContractTests(unittest.TestCase):
    def test_editor_html_is_markup_only_and_uses_relative_modules(self):
        html = HTML.read_text(encoding="utf-8")
        self.assertIn('href="editor.css"', html)
        self.assertIn('src="editor.js"', html)
        self.assertIn('href="/shared/framework.css"', html)
        self.assertIn('src="/shared/framework.js"', html)
        self.assertNotIn("<style", html)
        self.assertNotIn("<script>", html)

    def test_server_serves_only_known_relative_page_modules(self):
        source = SERVER.read_text(encoding="utf-8")
        self.assertIn("def send_page_module", source)
        self.assertIn('{"editor.js", "editor.css"}', source)
        self.assertIn('path in {"/editor.js", "/editor.css"}', source)

    def test_css_and_js_are_real_modules(self):
        self.assertTrue(JS.read_text(encoding="utf-8").strip().startswith('"use strict";'))
        self.assertIn(":root", CSS.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
