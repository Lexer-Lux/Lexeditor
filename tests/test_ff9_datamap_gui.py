"""FF9 Data Map GUI contract (issue #525).

Every openable Data Map row must resolve to a real editor tab declared in
plugins/ff9/editor.js, and every known-not-integrated p0data area must stay
visible but closed instead of becoming a raw-file placeholder.
"""
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def editor_tab_ids():
    text = (ROOT / "plugins/ff9/editor.js").read_text(encoding="utf-8")
    tabs = re.search(r"const tabs=\[(.*?)\];", text, re.DOTALL).group(1)
    return set(re.findall(r'\{id:"([^"]+)"', tabs))


class FF9DataMapGuiTests(unittest.TestCase):
    def rows(self):
        from plugins.ff9 import server
        fixture = [
            {"key": "one", "tab": "items", "relativePath": "one.csv",
             "label": "One", "controls": "Item data", "available": True},
            {"key": "two", "tab": "world", "relativePath": "two.csv",
             "label": "Two", "controls": "World data", "available": False},
        ]
        with tempfile.TemporaryDirectory() as name, \
                patch.object(server, "catalog", return_value=fixture), \
                patch.object(server.paths, "GAME_ROOT", Path(name)):
            return server.data_map()["rows"]

    def test_openable_rows_resolve_to_real_editor_tabs(self):
        from plugins.ff9 import server  # noqa: F401  (ensures module import path)
        tabs = editor_tab_ids()
        self.assertIn("enemies", tabs)
        self.assertIn("world", tabs)
        for row in self.rows():
            if row["openable"]:
                self.assertIn(row.get("target"), tabs,
                              f"Data Map row {row['filename']!r} opens nowhere")

    def test_unresolved_p0data_areas_stay_visible_but_closed(self):
        from plugins.ff9 import server
        rows = {(row["filename"], row["status"], row["coverage"], row["openable"])
                for row in self.rows()}
        for filename, _controls, _notes in server.UNRESOLVED_AREAS:
            self.assertIn((filename, "not-integrated", "unavailable", False), rows,
                          f"{filename!r} must stay visible and non-openable")


if __name__ == "__main__":
    unittest.main()
