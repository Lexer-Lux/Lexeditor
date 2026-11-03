"""Map geometry tags each texture with a content id for wire dedupe.

The Depths ships 727 texture blobs over the wire for 158 unique
images (104MB of a 157MB map open). Responses now carry
texture_ids alongside textures, and a known=id,... request omits
blobs the client already holds. Same name under different bytes
keeps distinct ids: two models can wear different images under
one name.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plugins.ds1.viewport import _payload

RED = b'\x89PNG-red-bytes'
BLUE = b'\x89PNG-blue-bytes'


def test_payload_tags_textures_with_stable_ids():
    first = _payload({'textures': {'tex0': RED}, 'meshes': []})
    second = _payload({'textures': {'tex0': RED}, 'meshes': []})
    assert first['texture_ids'] == second['texture_ids']
    assert set(first['texture_ids']) == {'tex0'}
    assert set(first['textures']) == {'tex0'}


def test_same_name_different_bytes_keeps_distinct_ids():
    left = _payload({'textures': {'tex0': RED}, 'meshes': []})
    right = _payload({'textures': {'tex0': BLUE}, 'meshes': []})
    assert left['texture_ids']['tex0'] != right['texture_ids']['tex0']


def test_known_ids_omit_blobs_but_keep_the_mapping():
    ids = _payload({'textures': {'tex0': RED, 'lit0': BLUE},
                    'meshes': []})['texture_ids']
    again = _payload({'textures': {'tex0': RED, 'lit0': BLUE}, 'meshes': []},
                     known=frozenset(ids.values()))
    assert again['textures'] == {}
    assert again['texture_ids'] == ids


def test_unknown_known_ids_are_ignored():
    payload = _payload({'textures': {'tex0': RED}, 'meshes': []},
                       known=frozenset({'no-such-id'}))
    assert set(payload['textures']) == {'tex0'}
