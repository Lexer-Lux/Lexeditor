"""DS1 panel contracts: per-tab list keys and unpaged record details.

1. Barrels, rows and detail columns are stored per tab and subtab, so two
   tabs keep different counts, and so does the divider split.
2. Every record-data detail flows into columns on a single scrolling page
   instead of paginating; the row remove button uses the shared SVG icon.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DS1 = (ROOT / "plugins" / "ds1" / "editor.js").read_text(encoding="utf-8")
UNPAGED = re.compile(r"paginate\s*:\s*\{\s*unpaged\s*:\s*true\s*\}")


def test_barrel_rows_and_columns_keys_carry_tab_and_sub():
    assert re.search(r"barrelKey\s*:\s*\"ds1-\"\s*\+\s*state\.tab\s*\+\s*\"-\"\s*\+\s*state\.sub", DS1) is not None
    assert re.search(r"rowsKey\s*:\s*\"ds1-\"\s*\+\s*state\.tab\s*\+\s*\"-\"\s*\+\s*state\.sub", DS1) is not None


def test_divider_split_is_per_tab():
    assert re.search(r"splitKey\s*:\s*\"ds1-\"\s*\+\s*state\.tab", DS1) is not None


def test_record_details_flow_unpaged():
    # Think record, asset file, both curve panels, the generic record panel
    # and both add/delete forms and tabbed record details: nine flows, no pagers.
    assert len(UNPAGED.findall(DS1)) == 9


def test_remove_button_uses_the_shared_icon():
    assert "LexeditorUI.removeIcon()" in DS1
    assert re.search(r"\}\s*,\s*\"x\"\s*\)", DS1) is None
