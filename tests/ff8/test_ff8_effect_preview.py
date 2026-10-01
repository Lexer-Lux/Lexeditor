from types import SimpleNamespace

from plugins.ff8.effect_preview import material_state


def test_material_state_uses_first_mesh_appearance():
    bone = SimpleNamespace(props=[(2, 'tex_op', (0x52, 0x52, (0,))),
                                  (3, 'mesh', 8),
                                  (9, 'tex_op', (0x92, 0x92, (99, 100)))])
    description = {'textures': [{'rect': (384, 256, 64, 128), 'depth': 8}],
                   'cluts': [{'rect': (320, 224, 256, 1)}]}
    assert material_state(SimpleNamespace(bones=[bone]), 8, description) == (3, 150, 14356)
    assert material_state(SimpleNamespace(bones=[bone]), 9, description) is None
