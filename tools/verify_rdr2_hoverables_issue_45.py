"""Source contract for typed RDR2 hoverables (GitHub #45)."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "games" / "rdr2" / "editor.html").read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


require("LexeditorUI.hoverable({content,targetType,targetId,targetLabel,activate" in SOURCE,
        "RDR2 must consume the shared hoverable component")
for target in (
    'targetType:"rdr2-item"', 'targetType:"rdr2-crafting-output"',
    'targetType:"rdr2-effect"', 'targetType:"rdr2-behavior"',
    'targetType:"rdr2-loot-table"', 'targetType:"rdr2-shop"',
    'targetType:"rdr2-weapon-record"', 'targetType:"rdr2-mob-archetype"',
):
    require(target in SOURCE, f"missing typed RDR2 target: {target}")

require('itemSel:key,itemPage:0' in SOURCE and 'itemSource:"all"' in SOURCE,
        "an Item jump must select the exact key and clear hiding filters")
require('effectSection:"effects",effQ:key,effectSel:key,effectPage:0' in SOURCE,
        "an Effect jump must select the exact effect")
require('effectSection:"behaviors",behaviorQ:id,behaviorSel:id,behaviorPage:0' in SOURCE,
        "a Behavior jump must select the exact behavior")
require('state.lootFile=file;navigate("loot",{lootQ:key,lootSel:key,lootPage:0})' in SOURCE,
        "a Loot jump must carry both file and table identity")
require('linkedCatalogKeyEditor(part.item' in SOURCE and 'itemLink(part.item)' in SOURCE,
        "editable and read-only Crafting ingredients must expose item hoverables")
require('itemLink(group.key,true' in SOURCE,
        "Crafting output mentions must expose item hoverables")
require('catalogItem(e.name)?itemLink(e.name' in SOURCE and
        'target?lootTableLink(target.file,target.table.key' in SOURCE,
        "Loot entry names must link only after typed target resolution")
require('title:"No catalog item with this name"' in SOURCE and
        'title:"No loot table with this name"' in SOURCE,
        "broken Loot references must remain visibly unresolved")
require('state.filters.effectSection="effects";state.filters.effQ=effect.key' not in SOURCE,
        "the old filter-only Behavior-to-Effect jump must not return")
require('navigate("items",{q:key,category:"",group:"",itemSection:"all"});' not in SOURCE,
        "the old filter-only Item jump must not return")

print("RDR2 typed hoverables issue 45 source contract passed")
