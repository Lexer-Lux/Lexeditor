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


target.RenderedTests.open = open_with_neutral

if __name__ == "__main__":
    unittest.main(module=target, verbosity=2)
