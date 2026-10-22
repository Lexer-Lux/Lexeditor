"""NPC model links come from map placements, not from NPC IDs.

Big Hat Logan (6030-6032) wears the player base model c0000 in every
map that places him; the Model tab follows the placement's model, and
a missing binder suppresses the tab instead of showing an empty
viewer. Synthetic map bytes, real linkage rule.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from msb_fixture import build_msb
from plugins.ds1.map_store import MapStore


def test_npc_models_follow_placement_models(tmp_path):
    game = tmp_path / "game"
    studio = game / "map" / "MapStudio"
    studio.mkdir(parents=True)
    (studio / "m17_00_00_00.msb").write_bytes(build_msb(
        parts=(("enemy", 2, 2, 0, 6031), ("enemy", 2, 6, 0, 6032)),
        models=(("c0000", 0),)))
    (studio / "m10_02_00_00.msb").write_bytes(build_msb(
        parts=(("enemy", 2, 11, 0, 6030),),
        models=(("c0000", 0),)))
    links = MapStore(str(game), None).npc_models()
    assert links[6030] == ["c0000"]
    assert links[6031] == ["c0000"]
    assert links[6032] == ["c0000"]
