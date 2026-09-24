#!/usr/bin/env python3
"""Static contract for Warband's issue #45 relationship links."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EDITOR = (ROOT / "plugins" / "warband" / "editor.js").read_text(encoding="utf-8")
SERVER = (ROOT / "plugins" / "warband" / "server.py").read_text(encoding="utf-8")


def require(text: str, source: str, message: str) -> None:
    if text not in source:
        raise AssertionError(message)


require('"fromId": parent', SERVER, "Upgrade sources do not expose a stable troop ID")
require('"toId": target', SERVER, "Upgrade targets do not expose a stable troop ID")
require("showAlert,hoverable", EDITOR, "Warband does not import the shared hoverable component")
require('targetType:"warband-troop",targetId:troopId', EDITOR,
        "Warband troop relationships are not typed by stable ID")
require('state.filters.troops="";state.filters.cut=false;state.selectedTroop=troopRowKey(troop)', EDITOR,
        "Troop navigation does not clear filters and select the exact source record")
require('state.pages.troops=0;navigate("troops")', EDITOR,
        "Troop navigation does not enter the target Table view")
if 'revealSelected:false' in EDITOR:
    raise AssertionError("Warband explicitly disables the shared selected-record reveal")
require('key:troopRowKey,selected:()=>state.selectedTroop', EDITOR,
        "Troop destination selection does not use unique source-record identity")

# Troop upgrades are now a shared tree graph rather than a from/to table. The
# relationship contract is the edge plus clickable stable-ID nodes, not a
# legacy hoverable cell in editor.html.
require('LexeditorUI.treeGraph({', EDITOR,
        "Warband troop upgrades do not use the shared tree graph")
require('edges:graph.edges', EDITOR,
        "the upgrade tree must draw the source relationship edges")
require('nodes:graph.nodes.map(node=>({id:node.id', EDITOR,
        "tree nodes must retain stable troop IDs")
require('select:node=>{state.selectedUpgrade=node.id', EDITOR,
        "selecting a tree node must select that exact troop")

print("Warband relationship navigation contract passed")
