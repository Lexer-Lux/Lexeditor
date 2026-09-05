"""Installed-asset and source contract for FF8 item-type icons."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import formats  # noqa: E402
from games.ff8.game_icons import ensure_icons, icon_path, item_icon_id  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    expected = {
        1: 223,    # Potion: character recovery
        36: 224,   # G-Potion: GF recovery
        22: 226,   # Shell Stone: battle item
        101: 227,  # Normal Ammo
        198: 228,  # magazine
        109: 229,  # refine/special item
    }
    require({item_id: item_icon_id(item_id) for item_id in expected} == expected,
            "installed mitem.bin types must follow FF8's executable icon table")
    require(item_icon_id(-1) is None and item_icon_id(999) is None,
            "invalid items must use the text-only fallback")
    manifest = ensure_icons()
    require(manifest.get("available") is True, "the installed FF8 icon atlas must be available")
    for icon_id in range(223, 230):
        target = icon_path(icon_id)
        require(target is not None and target.stat().st_size > 100,
                f"native item icon {icon_id} must be generated")
    rows = {row["id"]: row for row in formats.item_rows()["rows"]}
    require(all(rows[item_id]["iconId"] == icon_id for item_id, icon_id in expected.items()),
            "the Items API must expose each native type icon")
    require(all("iconId" in row for row in formats.item_choices()),
            "shop and weapon item choices must carry the same icon identity")

    editor = (ROOT / "games" / "ff8" / "editor.html").read_text(encoding="utf-8")
    require("function itemLabel(" in editor and "function itemSelectControl(" in editor,
            "FF8 must use shared item-label and selected-item helpers")
    require('render:row=>itemLabel(row)' in editor,
            "the Items list must prefix names with native icons")
    require('sharedDetail(row,prefs' in editor and 'itemIcon(row))' in editor,
            "the Items detail header must use the shared large icon slot")
    require("function itemSearchControl(" in editor and editor.count("itemSearchControl(") >= 3,
            "shops and weapon ingredients must use the shared visual item searcher")
    require("function itemSelectControl(" in editor,
            "finite item enums must keep the shared icon-aware select control")
    require("onerror:()=>image.remove()" in editor,
            "a missing PNG must remove itself instead of showing a broken image")
    print("FF8 installed item-icon contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
