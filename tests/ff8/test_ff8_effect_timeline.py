import struct

import pytest

from plugins.ff8.effect_timeline import PreviewSimulation, simulate


def script(*words):
    data = bytearray(48)
    struct.pack_into('<I', data, 4, 48)
    return bytes(data) + struct.pack(f'<{len(words)}H', *words)


def test_texture_and_palette_upload_order_is_preserved():
    result = simulate(script(0x27, 3, 0x29, 7, 0))
    assert result.vram_events == [(0, 'tex', (3,)), (0, 'clut', (3,)), (0, 'tex', (7,))]
    assert result.warnings == []


def test_wait_delays_following_upload():
    result = simulate(script(0x209, 0x27, 3, 0))
    assert result.vram_events[0][0] > 0


def test_instruction_budget_stops_non_yielding_loop(monkeypatch):
    monkeypatch.setattr(PreviewSimulation, 'MAX_INSTRUCTIONS', 20)
    with pytest.raises(ValueError, match='instruction budget'):
        simulate(script(2, 0))


def test_invalid_root_is_rejected():
    with pytest.raises(ValueError, match='root script'):
        simulate(bytes(50))


def test_shared_page_load_replaces_previous_upload_source():
    result = simulate(script(0xC006, 0x2029, 704, 256, 64, 256, 0))
    assert result.vram_events == [(0, 'rawrect', ((704, 256, 64, 256), 'ma8def_p.0'))]


def test_summon_file_slot_base_applies_to_streamed_loads():
    result = simulate(script(0xB2, 10, 0x8E06, 0x8029, 33, 0))
    assert result.vram_events == [(0, 'raw', (33, 17, 0))]


def test_shared_pages_ignore_summon_file_slot_base():
    result = simulate(script(0xB2, 10, 0xC006, 0x8029, 33, 0))
    assert result.vram_events == [(0, 'raw', (33, 'ma8def_p.0', 0))]


@pytest.mark.parametrize('opcode,handler', [(0x3C, 2), (0x56, 9)])
def test_scaled_and_clipped_mesh_selection_is_recorded(opcode, handler):
    words = (opcode, 8, 0) if opcode == 0x3C else (opcode, 8, 1, 0)
    result = simulate(script(*words))
    assert result.bones[0].prop('mesh', 0) == 8
    assert result.bones[0].prop('draw', 0) == handler
