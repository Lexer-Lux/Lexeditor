import struct

import pytest

from plugins.ff8 import effect_model_textures as materials, model_geometry
from plugins.ff8.vendor.ff8ue.glbbuilder import read_glb, read_accessor
from test_ff8_model_geometry import model_bytes


def tim():
    palette = struct.pack('<256H', 0, 31, *([0] * 254))
    return (struct.pack('<II', 16, 9) + struct.pack('<I4H', 524, 0, 0, 256, 1) + palette
            + struct.pack('<I4H', 12 + 65536, 0, 0, 128, 256) + bytes([1]) * 65536)


def test_atlas_offsets_and_palette_rows_are_preserved():
    region = {'depth': 8, 'x': 704, 'y': 256, 'width': 384, 'height': 256,
              'paletteX': 320, 'paletteY': 224, 'paletteWidth': 256, 'paletteHeight': 4}
    palette, uv = materials.match_material(region, 189, 14420, [(0, 0), (127, 255)])
    assert palette == 1
    assert uv == [(256 / 384, 0), (383 / 384, 255 / 256)]
    assert materials.match_material(region, 189, 14420, [(128, 0)]) is None
    assert materials.match_material(region, 189, 14421, [(0, 0)]) is None


def test_resolved_faces_and_glb_use_the_same_texture(tmp_path):
    exporter = model_geometry.decode('d0c000.dat', model_bytes())
    # The synthetic fixture uses a 4-bit page; select an 8-bit page for this TIM.
    exporter.ifrit_manager.enemy.geometry_data.object_data[0].triangles[0].tex_id_2 = 128
    materials.resolve(exporter, {'source.dat': tim()})
    assert exporter.unmapped_effect_faces == 0
    assert len(exporter.ifrit_manager.texture_data) == 1
    face = exporter._collect_triangulated_faces()[0]
    assert face[1] == ((0, 0), (255 / 256, 0), (0, 255 / 256))
    target = tmp_path / 'textured.glb'
    exporter.export(str(target))
    gltf, binary = read_glb(target)
    assert len(gltf['images']) == 1
    primitive = gltf['meshes'][0]['primitives'][0]
    assert read_accessor(gltf, binary, primitive['attributes']['TEXCOORD_0']) == list(face[1])


def test_ambiguous_or_missing_sources_do_not_guess():
    for sources in ({}, {'one.dat': tim(), 'two.dat': tim()}):
        exporter = model_geometry.decode('d0c000.dat', model_bytes())
        exporter.ifrit_manager.enemy.geometry_data.object_data[0].triangles[0].tex_id_2 = 128
        materials.resolve(exporter, sources)
        assert exporter.unmapped_effect_faces == 1
        assert exporter.ifrit_manager.texture_data == []
        assert exporter._collect_triangulated_faces()[0][2] < 0


def test_invalid_tim_coordinates_are_rejected():
    data = bytearray(tim())
    struct.pack_into('<H', data, 12, 900)
    with pytest.raises(ValueError, match='video memory'):
        materials.tim_region(data)


def test_explicit_source_resolves_only_matching_ambiguity(tmp_path):
    red = tim()
    green = bytearray(red)
    struct.pack_into('<H', green, 22, 31 << 5)
    images = {'red.dat': red, 'green.dat': bytes(green)}
    exporter = model_geometry.decode('d0c000.dat', model_bytes())
    exporter.ifrit_manager.enemy.geometry_data.object_data[0].triangles[0].tex_id_2 = 128
    materials.resolve(exporter, images, 'green.dat')
    assert exporter.unmapped_effect_faces == 0
    assert exporter.effect_texture_choices == ['green.dat', 'red.dat']
    from plugins.ff8 import assets
    expected = assets.tim_png_bytes(bytes(green))
    assert exporter.ifrit_manager.texture_data[0].texture_image == expected
    target = tmp_path / 'chosen.glb'
    exporter.export(str(target))
    gltf, binary = read_glb(target)
    span = gltf['bufferViews'][gltf['images'][0]['bufferView']]
    assert binary[span['byteOffset']:span['byteOffset'] + span['byteLength']] == expected
    with pytest.raises(ValueError, match='Unknown effect texture source'):
        materials.resolve(exporter, images, '../other.dat')
