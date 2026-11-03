"""World to Field subtab contract: field side kept, world side named as blocked.

The detail shows the field's name as a hoverable link with its background
picture and arrival point (rendering covered end to end by
ff8_wm2field_browser_check.py). The world-map side is blocked: wm2field.tbl
stores no world position and the trigger is not found yet, so the help says
exactly that instead of leaving the reader to wonder where the map went.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_arrival_section_promises_only_the_field_side():
    battle = (ROOT / "plugins/ff8/battle.js").read_text(encoding="utf-8")
    detail = battle[battle.index("function worldToFieldDetail"):battle.index("function renderWorldToField")]
    assert 'title:"ARRIVAL IN THE FIELD"' in detail
    assert "The world-map position that triggers each entry is not established yet" in detail
    # The field side stays: hoverable field name on top, background picture
    # with the arrival point beside the coordinates.
    assert 'targetType:"fields"' in detail
    assert "worldToFieldPicture(row,field)" in detail
    assert "drawWorldToFieldPoint(row,field,canvas,picture.geometry)" in battle
