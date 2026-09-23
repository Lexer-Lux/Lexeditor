from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "plugins" / "terraria" / "editor.html"
JS = ROOT / "plugins" / "terraria" / "editor.js"
CSS = ROOT / "plugins" / "terraria" / "editor.css"
SERVER = ROOT / "plugins" / "terraria" / "server.py"


class TerrariaUiContractTests(unittest.TestCase):
    def test_editor_html_is_markup_only_and_uses_relative_modules(self):
        html = HTML.read_text(encoding="utf-8")
        self.assertIn('href="editor.css"', html)
        self.assertIn('src="editor.js"', html)
        self.assertIn('href="/shared/framework.css"', html)
        self.assertIn('src="/shared/framework.js"', html)
        self.assertNotIn("<style", html)
        self.assertNotIn("<script>", html)

    def test_server_uses_shared_page_module_route(self):
        source = SERVER.read_text(encoding="utf-8")
        self.assertIn("PluginRequestHandler", source)
        self.assertIn("self.send_page_module(PLUGIN_ROOT, path)", source)
        self.assertNotIn("def send_page_module", source)

    def test_editor_uses_shared_data_views_and_shell_info(self):
        js = JS.read_text(encoding="utf-8")
        for token in (
            "pagedListDetail(", "columnList(", "LexeditorUI.dataMap(",
            'info:()=>navigate("info")', 'help:()=>navigate("datamap")',
            'tabbedPanel({tabs',
            'edit:(row,value)=>void editLocalizationCell(row,value)',
            'boolControl("noCompile")', 'boolControl("playableOnPreview")',
            'boolControl("translationMod")', "Not declared — check to add",
        ):
            self.assertIn(token, js)
        self.assertNotIn("confirm(", js)
        self.assertNotIn("terraria-map", js)
        self.assertNotIn("terraria-localization-table", js)
        for hook in (
            "terraria-record-view", "terraria-table", "terraria-full-page",
            "terraria-content-tabs", "terraria-localization-tabs",
            "terraria-loading", "terraria-note", "terraria-build-card",
            "terraria-source-editor", "terraria-asset-preview",
        ):
            self.assertNotIn(hook, js)

    def test_plugin_css_stays_small_and_does_not_reimplement_shared_components(self):
        css = CSS.read_text(encoding="utf-8")
        nonblank = [line for line in css.splitlines() if line.strip()]
        self.assertLessEqual(len(nonblank), 60)
        for forbidden in (".lex-pager{", ".lex-detail-panel{", ".lex-column-list{", ".lex-data-map{"):
            self.assertNotIn(forbidden, css)


if __name__ == "__main__":
    unittest.main()
