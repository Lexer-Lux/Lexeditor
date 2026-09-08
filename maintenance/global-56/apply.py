from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    assert text.count(old) == 1, f"unexpected context in {path}: {old[:80]!r}"
    p.write_text(text.replace(old, new), encoding="utf-8")


css = "ui/framework.css"
replace_once(
    css,
    "  font-family: inherit;\n  font-size: 12px;\n",
    "  /* The info-bubble glyph is shared chrome, not game typography.  A fixed\n"
    "     symbol stack keeps the ? metrics identical across plugin themes. */\n"
    "  font-family: var(--lex-symbol-font);\n  font-size: 12px;\n",
)
replace_once(
    css,
    ".lex-info-help > span {\n  display: block;\n}\n",
    ".lex-info-help > span {\n"
    "  display: grid;\n"
    "  width: 100%;\n"
    "  height: 100%;\n"
    "  place-items: center;\n"
    "  line-height: 1;\n"
    "  /* Punctuation sits optically low in the font's line box. */\n"
    "  transform: translateY(-0.5px);\n"
    "}\n",
)

test = ".github/scripts/ui_visual_acceptance.py"
replace_once(
    test,
    "              const lb=label.getBoundingClientRect(), hb=help?.getBoundingClientRect();\n"
    "              const range=document.createRange();\n",
    "              const lb=label.getBoundingClientRect(), hb=help?.getBoundingClientRect();\n"
    "              const glyph=help?.querySelector(':scope > span');\n"
    "              const gb=glyph?.getBoundingClientRect();\n"
    "              const hs=help?getComputedStyle(help):null, gs=glyph?getComputedStyle(glyph):null;\n"
    "              const range=document.createRange();\n",
)
replace_once(
    test,
    "                help:hb?{left:hb.left,right:hb.right,width:hb.width,height:hb.height,center:hb.left+hb.width/2}:null};\n",
    "                help:hb?{left:hb.left,right:hb.right,top:hb.top,bottom:hb.bottom,width:hb.width,height:hb.height,center:hb.left+hb.width/2}:null,\n"
    "                glyph:gb?{left:gb.left,right:gb.right,top:gb.top,bottom:gb.bottom,width:gb.width,height:gb.height,\n"
    "                  centerX:gb.left+gb.width/2,centerY:gb.top+gb.height/2,fontFamily:hs.fontFamily,transform:gs.transform}:null};\n",
)
replace_once(
    test,
    "                assert abs(first_geom['help']['width'] - first_geom['help']['height']) <= 0.5, (width, 'info bubble is not circular', first_geom)\n",
    "                assert abs(first_geom['help']['width'] - first_geom['help']['height']) <= 0.5, (width, 'info bubble is not circular', first_geom)\n"
    "                glyph = first_geom['glyph']\n"
    "                assert glyph, (width, 'info bubble ? glyph is missing', first_geom)\n"
    "                bubble_cx = first_geom['help']['left'] + first_geom['help']['width'] / 2\n"
    "                bubble_cy = first_geom['help']['top'] + first_geom['help']['height'] / 2\n"
    "                assert abs(glyph['centerX'] - bubble_cx) <= 0.75, (width, 'info bubble ? is not horizontally centered', first_geom)\n"
    "                assert abs(glyph['centerY'] - bubble_cy) <= 1.0, (width, 'info bubble ? is not vertically centered', first_geom)\n"
    "                assert 'Segoe UI Symbol' in glyph['fontFamily'], (width, 'info bubble inherited game typography', glyph)\n"
    "                assert glyph['transform'] != 'none', (width, 'info bubble lost its optical punctuation adjustment', glyph)\n",
)

# Leave the branch clean: this is transport machinery, not repository content.
Path(".github/workflows/global-56-one-shot.yml").unlink()
Path(__file__).unlink()
