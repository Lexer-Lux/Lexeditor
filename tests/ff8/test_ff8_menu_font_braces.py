"""The menu font must carry the braces the editor's text notation writes.

The Text tab writes tokens such as "{Griever}" and "{Wait030}" into game
messages. The atlas has no brace cell anywhere - its punctuation runs from the
parentheses to the quotes and then to the accented letters - so those
characters used to fall through to the fallback face and read as a different
font in the middle of menu text. The generated font now draws its own braces
from the parenthesis art.
"""
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from plugins.ff8 import game_font  # noqa: E402


def _atlas_available() -> bool:
    return all(path.is_file() for path in game_font._font_sources())


def test_the_atlas_itself_has_no_brace_cell():
    # The reason the font synthesizes: if the atlas ever gains a brace cell,
    # the drawn art below should be replaced by the real cell.
    assert "{" not in game_font.CHARACTERS and "}" not in game_font.CHARACTERS


def test_generated_font_covers_both_braces_with_real_glyphs():
    if not _atlas_available():
        pytest.skip("The FF8 menu font has not been extracted on this machine")
    from fontTools.ttLib import TTFont

    font = TTFont(str(game_font.ensure_font()))
    cmap = font.getBestCmap()
    for character in "{}":
        name = cmap.get(ord(character))
        assert name, f"the generated font has no {character!r}"
        glyph = font["glyf"][name]
        assert glyph.numberOfContours > 0, f"{character!r} is an empty glyph"
    # A brace is as wide as the parenthesis art it is drawn from, so text that
    # carries a token keeps the spacing the game font gave the rest of the line.
    paren = font["hmtx"][cmap[ord("(")]][0]
    assert font["hmtx"][cmap[ord("{")]][0] == paren
    assert font["hmtx"][cmap[ord("}")]][0] == paren
