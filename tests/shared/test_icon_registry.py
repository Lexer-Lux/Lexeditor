"""Every property-leading icon name resolves in the shared glyph registry.

detailField's icon is the one property-leading icon path: DS1 swaps in the
game's own menu art where it has a cell, and the shared TYPE_GLYPHS registry
(ui/framework.js) draws every other name. A name in neither renders nothing,
so these checks pin the fallback: each icon name any plugin's fields can send
must exist in TYPE_GLYPHS, spelled exactly as the plugin sends it.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def _glyph_block():
    text = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
    return text.split("const TYPE_GLYPHS = {", 1)[1].split("\n  };", 1)[0]


def _referenced_icon_names():
    from plugins.ds1.formats import _FIELD_ICONS, ABSORPTION_ICONS
    from plugins.ds1.icons import ICON_LABELS, LABELS
    from plugins.ff9.memoria_csv import _FIELD_ICONS as FF9_FIELD_ICONS
    return (set(LABELS) | set(ICON_LABELS) | set(_FIELD_ICONS.values())
            | set(ABSORPTION_ICONS.values()) | set(FF9_FIELD_ICONS.values()))


def test_every_referenced_icon_has_a_shared_glyph():
    glyphs = {match.group(1).lower()
              for match in re.finditer(r"^    ([A-Za-z0-9]+): \['#", _glyph_block(), re.MULTILINE)}
    assert glyphs, "the TYPE_GLYPHS block did not parse"
    missing = sorted(name for name in _referenced_icon_names() if name.lower() not in glyphs)
    assert not missing, f"icon names with no shared glyph fallback: {missing}"


def test_glyph_keys_match_the_names_plugins_send():
    verbatim = {match.group(1)
                for match in re.finditer(r"^    ([A-Za-z0-9]+): \['#", _glyph_block(), re.MULTILINE)}
    missing = sorted(name for name in _referenced_icon_names() if name not in verbatim)
    assert not missing, f"icon names with no verbatim glyph key: {missing}"


def test_ff9_gems_field_carries_its_icon():
    from plugins.ff9.memoria_csv import _FIELD_ICONS as FF9_FIELD_ICONS
    assert FF9_FIELD_ICONS.get("Gems") == "gems"
    editor = (ROOT / "plugins" / "ff9" / "editor.js").read_text(encoding="utf-8")
    assert re.search(r"detailField\(\{[^;]*?icon:field\.icon", editor), \
        "FF9 fieldControl drops field.icon before detailField"
