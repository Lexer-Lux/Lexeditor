from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
BANNERLORD_ROOT = ROOT / "games" / "bannerlord"
_STALE_DATA_MAP_MOUNT = re.compile(r"main\.replaceChildren\(\s*view\s*\)")


class BannerlordUiContractTests(unittest.TestCase):
    def test_data_map_layers_mount_shared_view_content(self) -> None:
        """Every Bannerlord Data Map renderer must mount the shared view's DOM content."""
        renderers = []
        offenders = []
        for path in sorted(BANNERLORD_ROOT.glob("editor_*.js")):
            text = path.read_text(encoding="utf-8")
            if "LexeditorUI.dataMap(" not in text:
                continue
            renderers.append(path.name)
            if _STALE_DATA_MAP_MOUNT.search(text):
                offenders.append(path.name)

        self.assertTrue(renderers, "Bannerlord must expose at least one shared Data Map renderer")
        self.assertEqual(
            offenders,
            [],
            "LexeditorUI.dataMap() returns a view object; mount view.content, not the view object: "
            + ", ".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
