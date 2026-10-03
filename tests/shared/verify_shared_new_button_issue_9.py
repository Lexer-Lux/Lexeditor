from pathlib import Path
from plugin_ui import plugin_ui


ROOT = Path(__file__).resolve().parents[2]
FRAMEWORK_JS = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
FRAMEWORK_CSS = (ROOT / "ui" / "framework.css").read_text(encoding="utf-8")
RDR2 = plugin_ui("rdr2")


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
# The later shared-button and drawn-plus changes supersede the private RDR2
# dashed/font treatment. One sizing token serves both pager and detail adds.
require('width: var(--lex-new-button-size, 32px)' in FRAMEWORK_CSS and
        'height: var(--lex-new-button-size, 32px)' in FRAMEWORK_CSS,
        "shared add controls must use the same square sizing token")
require('.lex-new-button-plus::before' in FRAMEWORK_CSS and
        '.lex-new-button-plus::after' in FRAMEWORK_CSS and
        'translate: -50% -50%' in FRAMEWORK_CSS,
        "the shared drawn plus must retain its centered horizontal and vertical bars")
for module in ("items", "effects", "loot", "crafting", "challenges", "shops"):
    require("newButton(" in (ROOT / "plugins/rdr2" / f"{module}.js").read_text(encoding="utf-8"),
            f"RDR2 {module} creation paths must use the shared primitive")
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
