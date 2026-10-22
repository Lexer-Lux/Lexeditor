"""DS1 text tags survive an edit round-trip byte-identical.

The text tab's <?tags?> are game codes (codex/ds1/text-tags.md), not
markup the editor owns: saving text that holds them must keep every
byte, and blank text stays refused.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_menu_archive
from plugins.ds1 import texts


def test_fmg_tag_text_roundtrips():
    blob = make_menu_archive(extra={"Dialogue_.fmg": {
        10: "Phantom <?joinName?> summoned",
        11: "Press <?attackR?>: <?sysmsg@1?>"}})
    document = texts.MenuDocument(blob)
    assert document.text("Dialogue_.fmg", 10) == "Phantom <?joinName?> summoned"
    document.set_text("Dialogue_.fmg", 10, "Phantom <?deadName?> was vanquished")
    again = texts.MenuDocument(document.export())
    assert again.text("Dialogue_.fmg", 10) == "Phantom <?deadName?> was vanquished"
    assert again.text("Dialogue_.fmg", 11) == "Press <?attackR?>: <?sysmsg@1?>"


def test_menu_label_tag_roundtrips():
    document = texts.MenuDocument(make_menu_archive())
    document.set_label("magicDefense", "MagDEF <?souls?>")
    again = texts.MenuDocument(document.export())
    assert again.label("magicDefense") == "MagDEF <?souls?>"
