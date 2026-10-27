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

def test_vanilla_length_text_saves():
    # Lexer: the 4,000 cap blocked text the game itself ships (vanilla's
    # longest entry is 9,886 characters). Vanilla-length text must save.
    document = texts.MenuDocument(make_menu_archive(extra={"Dialogue_.fmg": {10: "Seed"}}))
    long_text = "Lorem ipsum dolor sit amet. " * 380  # 9,880 characters
    assert len(long_text) > 4000
    assert document.set_text("Dialogue_.fmg", 10, long_text) == long_text
    again = texts.MenuDocument(document.export())
    assert again.text("Dialogue_.fmg", 10) == long_text


def test_absurd_text_reports_its_length():
    # Past the cap the error names the measured length, so a miscount
    # shows itself instead of reading as a false refusal.
    document = texts.MenuDocument(make_menu_archive(extra={"Dialogue_.fmg": {10: "Seed"}}))
    absurd = "x" * (texts.MAX_FMG_TEXT + 1)
    try:
        document.set_text("Dialogue_.fmg", 10, absurd)
    except texts.FormatError as error:
        assert str(len(absurd)) in str(error), error
    else:
        raise AssertionError("absurd text saved")
