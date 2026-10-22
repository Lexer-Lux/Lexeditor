"""Item property help says what is known, and says so when it is unknown."""
import json
from pathlib import Path
METADATA = Path(__file__).resolve().parents[2] / "plugins/ds1/metadata"
def description(relative, field):
    annotations = json.loads((METADATA / relative).read_text("utf-8-sig"))
    return next(entry["Description"] for entry in annotations["Fields"] if entry["Field"] == field)
def test_over_dexterity_says_unknown():
    # The Souls modding param wiki marks overDexterity Unknown on Magic, and
    # no source documents the Goods twin either. The old text ("Skill over
    # start value") explained nothing.
    for relative in ("annotations/EQUIP_PARAM_GOODS_ST.json", "annotations/MAGIC_PARAM_ST.json"):
        assert description(relative, "overDexterity").startswith("Unknown."), relative
