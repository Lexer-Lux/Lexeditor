"""Battle table scalars reject truncation and preserve opaque authored bytes."""
import pytest

from core.bounded import whole_number
from plugins.ffx_x2 import ctb_base, ffx_commands, ffx_auto_abilities, ffx2_abilities
from test_ffx_x2_ctb_base import _table as ctb_table
from test_ffx_x2_ffx_commands import _table as command_table, _record as command_record
from test_ffx_x2_ffx_auto_abilities import _table as auto_table, _record as auto_record
from test_ffx_x2_ffx2_abilities import _table as x2_table, _record as x2_record


@pytest.fixture(params=['ctb', 'auto', 'x2', *ffx_commands.TABLES])
def codec(request):
    return authored_codec(request.param)


def authored_codec(kind):
    if kind == 'ctb':
        raw = ctb_table([(10, 3), (20, 7)])
        return raw, ctb_base.apply_edits, dict(id=0, tickSpeed=255, icvBonus=0), {0x14: b'\xff\0'}
    if kind == 'auto':
        record = auto_record(strike=0xA1, absorb=0xA1, immune=0xA1, resist=0xA1, weak=0xA1)
        raw = auto_table([record, record])
        return raw, ffx_auto_abilities.apply_edits, dict(id=0, strike=31, absorb=0, immune=0, resist=0, weak=0), {0x25: bytes([0xBF, 0xA0, 0xA0, 0xA0, 0xA0])}
    if kind == 'x2':
        record = x2_record(1, 2, 3, 4, 5, 6)
        raw = x2_table([record, record])
        return raw, ffx2_abilities.apply_edits, dict(id=0, animation1=65535, animation2=0), {0x28: b'\xff\xff\0\0'}
    size = ffx_commands.TABLES[kind].record_size
    raw = command_table([command_record(5, 6, size)] * 2, record_size=size)
    return raw, lambda data, edits: ffx_commands.apply_table_edits(data, edits, kind), dict(id=0, animation1=65535, animation2=0), {0x24: b'\xff\xff\0\0'}


@pytest.mark.parametrize('value', [False, True, .5, float('inf'), float('-inf'), float('nan'), '1.5', None])
def test_battle_table_id_rejects_noninteger_values(codec, value):
    raw, apply, good, _ = codec
    with pytest.raises(ValueError, match='integer'):
        apply(raw, [good | dict(id=1), good | dict(id=value)])


@pytest.mark.parametrize('value', [False, .5, float('inf'), float('nan'), '1.5', None])
def test_battle_table_value_fields_reject_noninteger_values(codec, value):
    raw, apply, good, _ = codec
    for field in good.keys() - {'id'}:
        with pytest.raises(ValueError, match='whole number|integer'):
            apply(raw, [good | dict(id=1), good | {field: value}])


def test_battle_table_valid_bounds_preserve_all_other_bytes(codec):
    raw, apply, good, patches = codec
    expected = bytearray(raw)
    for offset, payload in patches.items():
        expected[offset:offset + len(payload)] = payload
    assert apply(raw, [good]) == expected
    assert apply(raw, [good | dict(id=0.0)]) == expected


@pytest.mark.parametrize('value', [.5, float('inf'), float('-inf'), float('nan'), True])
def test_shared_bounded_integer_rejects_truncation_and_overflow(value):
    class AuthoredError(ValueError):
        pass
    with pytest.raises(AuthoredError, match='whole number'):
        whole_number(value, 'Value', 0, 255, AuthoredError)
