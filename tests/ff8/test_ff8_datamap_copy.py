"""FF8 Data Map and card help copy stays one short line per string (8-1)."""
import re
from pathlib import Path

from plugins.ff8 import formats

ROOT = Path(__file__).resolve().parents[2]
LIMIT = 140


def test_data_map_copy_is_one_short_line():
    rows = formats.data_map_rows()["rows"]
    assert rows
    for row in rows:
        assert row["controls"].strip(), row["filename"]
        for key in ("controls", "notes"):
            text = row[key]
            assert "\n" not in text and "\r" not in text, (row["filename"], key)
            assert len(text) <= LIMIT, (row["filename"], key, len(text))


def test_card_player_help_is_one_short_line():
    source = (ROOT / "plugins" / "ff8" / "cards_ui.js").read_text(encoding="utf-8")
    block = re.search(r"const help=\[(.*?)\];", source, re.DOTALL).group(1)
    strings = re.findall(r'"(?:[^"\\]|\\.)*"', block)
    assert len(strings) >= 7
    for text in strings:
        assert len(text) - 2 <= LIMIT, text
