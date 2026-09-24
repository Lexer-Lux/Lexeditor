from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class GraphDesignATests(unittest.TestCase):
    def test_ff8_loads_the_approved_graph_renderer(self):
        bootstrap = (ROOT / "plugins/ff8/cards_ui.js").read_text(encoding="utf-8")
        self.assertNotIn("/shared/ff8-graph-design-a.js", bootstrap)
        self.assertFalse((ROOT / "ui/ff8-graph-design-a.js").is_file())
        self.assertFalse((ROOT / "ui/ff8-graph-design-a.css").is_file())

    def test_design_a_keeps_formula_transparent_and_unoutlined(self):
        css = (ROOT / "ui/framework.css").read_text(encoding="utf-8")
        self.assertIn("background:transparent", css)
        self.assertIn("text-shadow:", css)
        self.assertIn("var(--lex-math-font", css)
        self.assertIn(".lex-math-formula > math", css)
        self.assertIn(".lex-curve-path-formula", css)

    def test_renderer_uses_real_curve_geometry_and_math_structure(self):
        script = (ROOT / "ui/framework.js").read_text(encoding="utf-8")
        self.assertIn("line.getTotalLength()", script)
        self.assertIn("line.getPointAtLength", script)
        self.assertIn("svg.getScreenCTM()", script)
        self.assertIn('node("mfrac", left, right)', script)
        self.assertIn('node("msup", left, right)', script)

    @unittest.skipUnless(shutil.which("node"), "Node.js is not installed in this test environment")
    def test_renderer_javascript_parses(self):
        subprocess.run(
            [shutil.which("node"), "--check", str(ROOT / "ui/framework.js")],
            check=True,
            cwd=ROOT,
        )


if __name__ == "__main__":
    unittest.main()
