"""Reordered texture packs reuse only exact installed bytes, without compression."""
import pytest
from plugins.ds1 import texture_packs, formats
from test_ds1_assets import make_tpf, make_dds
from test_ds1_deflate_reuse import dcx


@pytest.fixture
def packs(monkeypatch):
    image = make_dds()
    other = image[:-1] + bytes([image[-1] ^ 1])
    monkeypatch.setattr(texture_packs, 'menu_texture_names', lambda _: ['B', 'A'])
    main = dcx(make_tpf([('A', image)]))
    split = dcx(make_tpf([('B', other)]))
    header, rows = texture_packs.read(make_tpf([('B', other), ('A', image)]))
    installed = dcx(texture_packs.write(header, rows))
    return main, split, installed


def test_exact_installed_pack_avoids_compression_even_without_output_cache(packs, monkeypatch):
    main, split, installed = packs
    def unnecessary(*_args, **_kwargs):
        pytest.fail('The already-installed desired texture pack was compressed again')
    monkeypatch.setattr(formats, 'deflate', unnecessary)
    assert texture_packs.align_menu(b'layout', main, [split], current=installed) == installed


@pytest.mark.parametrize('candidate', ['wrong_pixels', 'wrong_order', 'damaged'])
def test_stale_or_damaged_installed_pack_is_not_reused(packs, monkeypatch, candidate):
    main, split, installed = packs
    image = make_dds()
    current = (dcx(make_tpf([('B', image), ('A', image)])) if candidate == 'wrong_pixels' else
               dcx(make_tpf([('A', image), ('B', image)])) if candidate == 'wrong_order' else b'DCX\0damaged')
    result = texture_packs.align_menu(b'layout', main, [split], current=current)
    assert result != current
    assert formats.inflate(result) == formats.inflate(installed)
