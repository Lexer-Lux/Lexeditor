from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRAMEWORK_JS = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
FRAMEWORK_CSS = (ROOT / "ui" / "framework.css").read_text(encoding="utf-8")
RDR2 = (ROOT / "games" / "rdr2" / "editor.html").read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


require("const newButton =" in FRAMEWORK_JS and "newButton," in FRAMEWORK_JS,
        "the shared framework must export one New/Add button primitive")
require("lex-new-button lex-ui-symbol" in FRAMEWORK_JS,
        "the primitive must own one semantic class and safe plus font")
require(".lex-new-button" in FRAMEWORK_CSS,
        "the shared primitive needs a plugin-neutral default style")
require("const newButton=window.LexeditorUI.newButton;" in RDR2,
        "RDR2 must consume the shared primitive instead of rebuilding it")
require("button.lex-new-button" in RDR2 and "border:1px dashed var(--border)" in RDR2,
        "the RDR2 theme must own the requested dark dashed treatment")
require("font:400 27px/1 var(--rdr-font-display)" in RDR2,
        "the RDR2 plus must use the installed Redemption display face")
require("transform:translateY(2px)" in RDR2,
        "the RDR2 theme must correct the display face's plus-glyph metrics once")
require(RDR2.count("newButton(") >= 20,
        "all RDR2 creation paths must use the shared primitive")
require('newButton({title:"Add recipe",onclick:toggleRecipe})' in RDR2,
        "the empty Items Recipe field must use the shared Add control")
require('}"Add recipe")' not in RDR2 and '},"Add recipe")' not in RDR2,
        "the Items Recipe field must not rebuild a visible Add recipe button")

for old in (
    '"+ NEW ITEM"', '"+ NEW EFFECT"', '"+ rule"', '"+ slot"',
    '"+ ingredient"', '"+ add recipe"', '"+ another recipe"',
    '"+ CONDITION"', '"+ GROUP"', '"+ add item to this shop"',
    '"+ recipe"', '"+ NEW GROUP"', '"+ NEW TABLE"', '"+ item"',
    '"+ table / group"', '"+ yield"', '"+ add row"', '"+ reward"',
):
    require(old not in RDR2, f"hand-built visible Add label remains: {old}")

print("shared New button issue 9 source contract passed")
