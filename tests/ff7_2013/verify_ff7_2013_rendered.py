"""Rendered FF7 2013 save/discard acceptance against the current shared page modules."""
from __future__ import annotations

# Dev caches and outputs live in the temp folder, never in the checkout.
DEV_CACHE = __import__("pathlib").Path(__import__("tempfile").gettempdir()) / "lexeditor-dev"
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str((ROOT / "tools").resolve()))

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ff7"))
import verify_ff7_rendered_neutral as neutral

target = neutral.target
OUT = DEV_CACHE / "ff7-2013-acceptance"


def open_current_modules(self, edition: str = "ff7") -> None:
    """Load the same FF7 page code as production, including the split editor.js modules."""
    self.page.goto("about:blank")
    html = (ROOT / "plugins" / "ff7" / "editor.html").read_text(encoding="utf-8")
    html = html.replace("<head>", '<head><base href="http://127.0.0.1:9/">', 1)
    shared_css = (
        (ROOT / "ui" / "framework.css").read_text(encoding="utf-8")
        + "\n"
        + (ROOT / "ui" / "neutral.css").read_text(encoding="utf-8")
    )
    html = html.replace(
        '<link rel="stylesheet" href="/shared/framework.css">',
        "<style>" + shared_css + "</style>",
    )
    html = html.replace('<link rel="stylesheet" href="/shared/neutral.css">', "")
    bootstrap = (
        target.HOST
        + "\nwindow.__lexeditorPlugin="
        + json.dumps({"id": edition, "name": "FF7 fixture", "edition": edition})
        + ";\n"
        + (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
    )
    html = html.replace(
        '<script src="/shared/framework.js"></script>',
        "<script>" + bootstrap + "</script>",
    )
    scripts = "".join("<script>" + (ROOT / "plugins" / "ff7" / name).read_text(encoding="utf-8") + "</script>" for name in ("editor.js", "controls.js", "details.js", "workspace.js"))
    html = html.replace('<script src="editor.js"></script>', scripts)
    for extra in ("controls.js", "details.js", "workspace.js"):
        html = html.replace('<script src="%s"></script>' % extra, "")
    self.page.set_content(html, wait_until="domcontentloaded")
    self.page.wait_for_function("typeof state !== 'undefined' && state.loaded === true")
    self.assertEqual(self.errors, [])


class FF72013Discard(target.RenderedTests):
    open = open_current_modules

    def test_discard_restores_saved_baseline(self) -> None:
        self.install()
        self.page.set_viewport_size({"width": 900, "height": 620})
        self.open("ff7-2013")

        # Verify the Data Map itself through the shared page navigation contract.
        # The shell button's exact title is shared-UI copy owned by PR #485.
        self.page.evaluate('navigate("datamap")')
        self.page.wait_for_function("state.tab === 'datamap'")
        self.assertTrue(self.page.locator(".lex-data-map-view").is_visible())
        coverage = self.page.get_by_label("Filter files by integration", exact=True)
        self.assertIn("Partial", coverage.locator("option").all_inner_texts())

        self.navigate("armor")
        control = self.control("armor", "defense")
        self.assertEqual(control.get_attribute("type"), "number")
        self.assertIsNotNone(control.get_attribute("min"))
        self.assertIsNotNone(control.get_attribute("max"))
        self.assertGreater(self.page.locator(".ff7-detail .lex-info-help").count(), 0)

        OUT.mkdir(parents=True, exist_ok=True)
        self.page.screenshot(path=str(OUT / "ff7-2013-900x620.png"))

        # Reopen the exact same UI at a real 1.5 device scale factor. This models
        # 150% display scaling without changing application CSS or page zoom.
        self.page.close()
        self.page = self.browser.new_page(
            viewport={"width": 900, "height": 620},
            device_scale_factor=1.5,
        )
        self.page.set_default_timeout(10000)
        self.errors = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.expose_function("testRequest", self.bridge)
        self.open("ff7-2013")
        self.navigate("armor")
        control = self.control("armor", "defense")
        self.assertEqual(self.page.evaluate("window.devicePixelRatio"), 1.5)
        metrics = self.page.evaluate(
            """()=>{const r=document.querySelector('.ff7-detail').getBoundingClientRect();
            return {right:r.right,bottom:r.bottom,width:innerWidth,height:innerHeight}}"""
        )
        self.assertLessEqual(metrics["right"], metrics["width"] + 2, metrics)
        self.assertLessEqual(metrics["bottom"], metrics["height"] + 2, metrics)
        self.page.screenshot(path=str(OUT / "ff7-2013-900x620-150pct.png"))

        original = int(control.input_value())
        changed = original + 1 if original < 255 else original - 1
        control.fill(str(changed))
        self.page.wait_for_function("dirtyCount() > 0")
        self.page.locator("#global-save").click(button="right")
        dialog = self.page.locator(".lex-discard-dialog")
        dialog.wait_for(state="visible")
        self.page.screenshot(path=str(OUT / "ff7-2013-discard-confirmation.png"))
        dialog.get_by_role("button", name="Discard Changes", exact=True).click()
        self.page.wait_for_function("dirtyCount() === 0")
        restored = self.control("armor", "defense")
        self.assertEqual(int(restored.input_value()), original)
        self.page.screenshot(path=str(OUT / "ff7-2013-after-discard.png"))
        self.originals_unchanged()
        self.assertEqual(self.errors, [])


if __name__ == "__main__":
    suite = unittest.TestSuite(
        [FF72013Discard("test_discard_restores_saved_baseline")]
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
