from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
BANNERLORD_ROOT = ROOT / "plugins" / "bannerlord"
_STALE_DATA_MAP_MOUNT = re.compile(r"main\.replaceChildren\(\s*view\s*\)")


class BannerlordUiContractTests(unittest.TestCase):
    def test_editor_html_is_markup_only_and_uses_relative_page_modules(self) -> None:
        html = (BANNERLORD_ROOT / "editor.html").read_text(encoding="utf-8")
        self.assertNotIn("<style", html.lower())
        self.assertIsNone(re.search(r"<script(?![^>]*\bsrc=)[^>]*>", html, re.I))
        self.assertIn('href="./editor.css"', html)
        self.assertIn('src="./editor_shared.js"', html)
        self.assertNotIn('/bannerlord/editor_', html)

        server = (BANNERLORD_ROOT / "server.py").read_text(encoding="utf-8")
        self.assertIn("def send_page_module(", server)
        self.assertIn('path == "/editor.css"', server)
        self.assertIn('path.startswith("/editor_")', server)

    def test_plugin_css_stays_small_and_does_not_rebuild_shared_tables(self) -> None:
        css = (BANNERLORD_ROOT / "editor.css").read_text(encoding="utf-8")
        substantive = [line for line in css.splitlines() if line.strip() and not line.lstrip().startswith("/*")]
        self.assertLessEqual(len(substantive), 60)
        for selector in (".lex-column-list", ".lex-pager", ".lex-detail-panel", ".lex-settings-columns"):
            self.assertNotIn(selector, css)

    def test_shell_uses_shared_info_and_data_map_without_fake_tabs(self) -> None:
        boot = (BANNERLORD_ROOT / "editor_boot.js").read_text(encoding="utf-8")
        self.assertIn('help:()=>navigate("datamap")', boot)
        self.assertIn('info:()=>navigate("info")', boot)
        self.assertIn('{id:"tweaks",label:"Tweaks"}', boot)
        shell_block = boot[boot.index("const shell=LexeditorUI.mountShell"):boot.index("const runtimeRequest=", boot.index("const shell=LexeditorUI.mountShell"))]
        self.assertNotIn('id:"deployment"', shell_block)
        self.assertNotIn('id:"datamap"', shell_block)
        self.assertNotIn('id:"settings"', shell_block)

    def test_shared_table_detail_and_tweaks_components_are_used(self) -> None:
        shared = (BANNERLORD_ROOT / "editor_shared.js").read_text(encoding="utf-8")
        settings = (BANNERLORD_ROOT / "editor_settings.js").read_text(encoding="utf-8")
        for token in ("LexeditorUI.pagedListDetail", "LexeditorUI.columnList", "LexeditorUI.detailPanel",
                      "LexeditorUI.tabbedPanel", "LexeditorUI.infoHelp"):
            self.assertIn(token, shared)
        self.assertIn("BLUI.settingsColumns(", settings)
        self.assertIn('typeof LexeditorUI.paginateSettings==="function"', settings)
        self.assertIn("BLUI.pager(", settings)  # branch-framework fallback only

    def test_data_map_layers_mount_shared_view_content(self) -> None:
        renderers, offenders = [], []
        for path in sorted(BANNERLORD_ROOT.glob("editor_*.js")):
            text = path.read_text(encoding="utf-8")
            if "LexeditorUI.dataMap(" not in text:
                continue
            renderers.append(path.name)
            if _STALE_DATA_MAP_MOUNT.search(text):
                offenders.append(path.name)
        self.assertTrue(renderers)
        self.assertEqual(offenders, [])

    def test_info_records_native_loader_and_external_toolchain_boundaries(self) -> None:
        shared = (BANNERLORD_ROOT / "editor_shared.js").read_text(encoding="utf-8")
        self.assertIn("Bannerlord native module system", shared)
        self.assertIn("no Bannerlord helper entry", shared)
        self.assertIn("System dotnet SDK", shared)
        self.assertIn("does not install or auto-update", shared)
        self.assertIn("not bundled or redistributed", shared)
        self.assertIn("bannerlordModLoaderSection()", shared)

    def test_build_ui_exposes_msbuild_execution_trust_boundary(self) -> None:
        text = (BANNERLORD_ROOT / "editor_build.js").read_text(encoding="utf-8")
        self.assertIn("MSBuild targets run with your user permissions", text)
        self.assertIn("not a sandbox", text)
        self.assertIn("Build only projects you trust", text)

    def test_global_discard_reloads_structured_and_source_state(self) -> None:
        boot = (BANNERLORD_ROOT / "editor_boot.js").read_text(encoding="utf-8")
        self.assertIn("async function discardAllChanges()", boot)
        self.assertIn("discard:discardAllChanges", boot)
        self.assertIn('/api/runtime-overrides', boot)
        self.assertIn('/api/module-data?path=', boot)
        self.assertIn('/api/gauntlet?path=', boot)
        self.assertIn('/api/source?path=', boot)


if __name__ == "__main__":
    unittest.main()
