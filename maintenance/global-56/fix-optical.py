from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    assert text.count(old) == 1, f"unexpected context in {path}: {old[:80]!r}"
    p.write_text(text.replace(old, new), encoding="utf-8")

css = "ui/framework.css"
replace_once(
    css,
    "  /* Punctuation sits optically low in the font's line box. */\n  transform: translateY(-0.5px);\n",
    "  /* Punctuation sits optically low in the font's line box.  Use relative\n"
    "     positioning rather than transform: label-fitting code may legitimately\n"
    "     own transforms on descendants. */\n"
    "  position: relative;\n"
    "  top: -0.5px;\n",
)

test = ".github/scripts/ui_visual_acceptance.py"
replace_once(
    test,
    "                  centerX:gb.left+gb.width/2,centerY:gb.top+gb.height/2,fontFamily:hs.fontFamily,transform:gs.transform}:null};\n",
    "                  centerX:gb.left+gb.width/2,centerY:gb.top+gb.height/2,fontFamily:hs.fontFamily,top:gs.top}:null};\n",
)
replace_once(
    test,
    "                assert glyph['transform'] != 'none', (width, 'info bubble lost its optical punctuation adjustment', glyph)\n",
    "                assert glyph['top'] == '-0.5px', (width, 'info bubble lost its optical punctuation adjustment', glyph)\n",
)

Path(".github/workflows/global-56-optical-one-shot.yml").unlink()
Path(__file__).unlink()
