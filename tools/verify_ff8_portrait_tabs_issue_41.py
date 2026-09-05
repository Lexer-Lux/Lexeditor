"""Static and generated-asset contract for Lexeditor issue 41."""

from __future__ import annotations

import json
from pathlib import Path
import sys

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8.game_icons import ensure_portraits, portrait_root  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    editor = (ROOT / "games" / "ff8" / "editor.html").read_text(encoding="utf-8")
    manifest = ensure_portraits()
    require(manifest.get("available"), "installed mngrp.bin portrait sheets must decode")
    require(set(manifest["portraits"]) == {"characters", "gfs"},
            "the manifest must keep characters and GFs separate")
    require(len(manifest["portraits"]["characters"]) == 11,
            "all 11 editable section-7 characters need portraits")
    require(len(manifest["portraits"]["gfs"]) == 16,
            "all 16 editable section-3 GFs need portraits")
    for group in manifest["portraits"].values():
        for filename in group.values():
            with Image.open(portrait_root() / filename) as image:
                require(image.size == (32, 48), f"{filename} is not one portrait cell")
    require("function portraitTabs(view,rows,selected,detailId,select)" in editor,
            "GFs and Characters must use one portrait selector")
    require('portraitTabs("gfs",rows,row.id,"gf-detail"' in editor,
            "GFs must use the shared portrait selector")
    require('portraitTabs("characters",rows,row.id,detailId' in editor,
            "Characters must use the shared portrait selector")
    require('class:"ff8-portrait-selector"' in editor and 'class:"ff8-portrait-selected-name"' in editor
            and 'class:"ff8-portrait-selected-id"' in editor,
            "the selector row must show selected name left and shared prefixed ID right")
    render_characters = editor[editor.index("function renderCharacters"):
                               editor.index("const gfPanelOrder")]
    require("detailHead(row)" not in render_characters,
            "Characters must not repeat the selected name and ID in a large detail header")
    gf_panel = editor[editor.index("function gfPanel"):
                      editor.index("function gfAbilities")]
    require("recordId(row.id" not in gf_panel,
            "the GF General panel must not repeat the selected ID")
    require('src:`/assets/portraits/${view}/${row.id}.png`' in editor,
            "portrait buttons must use generated installed-game art")
    require('"aria-label":row.name,title:row.name' in editor,
            "portrait-only tabs need hover and accessible names")
    require('class:"ff8-portrait-fallback"' in editor and 'missing-portrait' in editor,
            "missing portraits need an explicit fallback")
    require('characters:renderCharacters' in editor,
            "Characters must not remain on the generic master list")
    require('role:"tabpanel"' in editor and '"aria-selected":String(row.id===selected)' in editor,
            "the portrait selector must expose tab state")
    require(".ff8-portrait-tab{position:relative;display:grid;width:100%;min-width:0;aspect-ratio:2/3;padding:0" in editor,
            "portrait buttons must use the source portrait aspect ratio without internal blank space")
    require(".ff8-portrait-tab img{position:absolute;inset:0;display:block;width:100%;height:100%;object-fit:cover" in editor,
            "portrait art must fill the full portrait-shaped button")
    require("height:58px" not in editor and ".ff8-portrait-tab img{width:32px;height:48px" not in editor,
            "the old short landscape buttons and small fixed images must not return")
    require('body:characterDetail(row)' in editor,
            "Characters must route their fixed detail sections through one character detail builder")
    groups = editor[editor.index("function fieldGroups"):
                    editor.index("function gfCompatibilityFormat")]
    require("function fieldGroups(fields,view,rowId,collapsible=true,prefs=null)" in groups
            and 'detailSection({className:"field-group",title:name' in groups,
            "field groups must use the shared fixed section header")
    require('el("details"' not in groups and 'el("summary"' not in groups,
            "character field groups must not return to collapsed disclosure widgets")
    require('class:`ff8-gender ${Number(gender.value)===1?"female":"male"}`' in editor,
            "character gender must be a colored, direct Mars or Venus control beside the name")
    print(json.dumps({
        "characters": len(manifest["portraits"]["characters"]),
        "gfs": len(manifest["portraits"]["gfs"]),
        "portraitSize": [32, 48],
        "source": "private mngrp.bin face1.tim and face2.tim",
        "sharedSelector": "portraitTabs",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
