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
