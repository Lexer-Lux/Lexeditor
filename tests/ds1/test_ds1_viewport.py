"""Viewport data on synthetic maps and models; no proprietary game bytes."""
import base64
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from flver_fixture import build_flver
from msb_fixture import build_msb
from plugins.ds1.flver import FlverError
from plugins.ds1.map_store import MapStore
from plugins.ds1.msb import MAP_DIR, MsbError
from plugins.ds1 import viewport

MAP = "test.msb"


def setup(tmp_path):
    game = tmp_path / "game"
    (game / MAP_DIR).mkdir(parents=True, exist_ok=True)
    (game / MAP_DIR / MAP).write_bytes(build_msb())
    (game / "map" / "test").mkdir(parents=True, exist_ok=True)
    (game / "map" / "test" / "m10piece.flver").write_bytes(build_flver())
    return MapStore(game, None, True)


def test_map_view_lists_parts_and_model_availability(tmp_path):
    view = viewport.map_view(setup(tmp_path), MAP)
    assert view["map"] == MAP
    assert view["models"] == {"c1200": {"type": 0, "available": False, "reason": "no model file"},
                              "m10piece": {"type": 0, "available": True, "reason": ""}}
    kinds = [(part["name"], part["kind"], part["model"]) for part in view["parts"]]
    assert kinds == [("enemy0", "Enemy", "c1200"), ("player0", "Player", "m10piece"),
                     ("piece0", "Map piece", "m10piece"), ("chest0", "Object", "m10piece")]
    assert view["parts"][0]["pos"] == [1.0, 2.0, 3.0]
    assert view["parts"][0]["scale"] == [1.0, 1.0, 1.0]
    with pytest.raises(MsbError):
        viewport.map_view(setup(tmp_path), "missing.msb")


def test_model_geometry_decodes_to_viewport_arrays(tmp_path):
    store = setup(tmp_path)
    model = next(entry for entry in store.get(MAP).models if entry["name"] == "m10piece")
    geometry = viewport.model_geometry(store.game_root, None, MAP, model)
    assert len(geometry["meshes"]) == 1
    mesh = geometry["meshes"][0]
    assert (mesh["verts"], mesh["tris"]) == (4, 2)
    positions = struct.unpack("<12f", base64.b64decode(mesh["positions"]))
    assert positions[:3] == (0.0, 0.0, 0.0) and positions[3:6] == (1.0, 0.0, 0.0)
    indices = struct.unpack("<6I", base64.b64decode(mesh["indices"]))
    assert indices == (0, 1, 2, 0, 2, 3)  # flipped to counter-clockwise for WebGL
    assert len(base64.b64decode(mesh["normals"])) == 48
    assert mesh["cull"] is True and mesh["mat_def"] == "M[D].mtd"
    missing = next(entry for entry in store.get(MAP).models if entry["name"] == "c1200")
    with pytest.raises(FlverError):
        viewport.model_geometry(store.game_root, None, MAP, missing)
