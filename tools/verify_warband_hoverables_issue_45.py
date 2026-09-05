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
require('render:row=>troopLink(row.fromId,row.from)', EDITOR,
        "Upgrade source mentions are not hoverable")
require('render:row=>troopLink(row.toId,row.to)', EDITOR,
        "Upgrade target mentions are not hoverable")

print("Warband hoverable relationship contract passed")
