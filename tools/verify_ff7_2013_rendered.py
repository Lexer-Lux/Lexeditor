"""Rendered FF7 2013 save/discard acceptance against the current shared page modules."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str((ROOT / "tools").resolve()))

import verify_ff7_rendered_neutral as neutral

target = neutral.target
OUT = ROOT / "out" / "ff7-2013-acceptance"


def open_current_modules(self, edition: str = "ff7") -> None:
    """Load the same FF7 page code as production, including the split editor.js module."""
    self.page.goto("about:blank")
    html = (ROOT / "games" / "ff7" / "editor.html").read_text(encoding="utf-8")
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
    html = html.replace('<script src="editor.js"></script>', "")
    self.page.set_content(html, wait_until="domcontentloaded")
    self.page.add_script_tag(
        content=(ROOT / "games" / "ff7" / "editor.js").read_text(encoding="utf-8")
    )
    self.page.wait_for_function("state.loaded === true")
    self.assertEqual(self.errors, [])


class FF72013Discard(target.RenderedTests):
    open = open_current_modules

    def test_discard_restores_saved_baseline(self) -> None:
        self.install()
        self.open("ff7-2013")
        self.navigate("armor")
        control = self.control("armor", "defense")
        original = int(control.input_value())
        changed = original + 1 if original < 255 else original - 1
        control.fill(str(changed))
        self.page.wait_for_function("dirtyCount() > 0")
        self.page.locator("#global-save").click(button="right")
        dialog = self.page.locator(".lex-discard-dialog")
        dialog.wait_for(state="visible")
        OUT.mkdir(parents=True, exist_ok=True)
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
