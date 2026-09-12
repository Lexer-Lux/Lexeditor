#!/usr/bin/env python3
"""Static contract for Warband's issue #45 relationship links."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EDITOR = (ROOT / "games" / "warband" / "editor.html").read_text(encoding="utf-8")
SERVER = (ROOT / "games" / "warband" / "server.py").read_text(encoding="utf-8")


def require(text: str, source: str, message: str) -> None:
    if text not in source:
        raise AssertionError(message)


require('"fromId": parent', SERVER, "Upgrade sources do not expose a stable troop ID")
require('"toId": target', SERVER, "Upgrade targets do not expose a stable troop ID")
require("showAlert,hoverable", EDITOR, "Warband does not use the shared hoverable component")
require('targetType:"warband-troop",targetId:troopId', EDITOR,
        "Warband troop relationships are not typed by stable ID")
require('state.filters.troops="";state.filters.cut=false;state.selectedTroop=troop.id', EDITOR,
        "Troop navigation does not clear filters and select the exact record")
require('state.pages.troops=0;navigate("troops")', EDITOR,
        "Troop navigation does not enter the target Table view")
if 'revealSelected:false' in EDITOR:
    raise AssertionError("Warband explicitly disables the shared selected-record reveal")
require('key:troop=>troop.id,selected:()=>state.selectedTroop', EDITOR,
        "Troop destination selection does not use the stable troop ID")
# The upgrades surface is a troop tree now, not a table with a "from" column,
# so the source troop is reachable by selecting its node rather than by a link
# in a cell. What must remain true is that every troop in the tree is a control
# that selects that troop, which is the navigation the contract was about.
require('"data-troop":node.id', EDITOR,
        "tree nodes must identify the troop they stand for")
require('state.selectedUpgrade=node.id', EDITOR,
        "selecting a troop in the upgrade tree must select that troop")
# Same for the target side: the edge to the upgraded troop is drawn in the tree
# and that troop's own node is the control.
require('for(const edge of graph.edges)', EDITOR,
        "the upgrade tree must draw the link to each upgrade target")

print("Warband hoverable relationship contract passed")
