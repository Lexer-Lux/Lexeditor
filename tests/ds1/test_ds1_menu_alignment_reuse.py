"""Reordered texture packs reuse only exact installed bytes, without compression."""
import pytest
from pathlib import Path
from unittest.mock import Mock

from plugins.ds1 import texture_packs, formats, mod_loader, composition_cache, deployment
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


@pytest.fixture
def alignment(packs, monkeypatch, tmp_path):
    main, split, installed = packs
    game = tmp_path / 'game'
    (game / 'menu').mkdir(parents=True)
    (game / 'menu/menu.tpf.dcx').write_bytes(main)
    (game / 'menu/menu_0.tpf.dcx').write_bytes(split)
    monkeypatch.setattr(deployment, 'vanilla_source', lambda root, relative: root / relative)
    monkeypatch.setattr(composition_cache, 'user_root', lambda: tmp_path / 'cache')
    align = Mock(wraps=texture_packs.align_menu)
    monkeypatch.setattr(texture_packs, 'align_menu', align)

    def run(layout=b'layout', files=None):
        result = mod_loader.Composition(dict(files or {}), [])
        mod_loader.align_menu_textures(game, result, layout)
        return result.files[Path('menu/menu.tpf.dcx')]

    return game, run, align, installed


def test_unchanged_alignment_reuses_bounded_output_cache(alignment):
    _game, run, align, installed = alignment
    assert formats.inflate(run()) == formats.inflate(installed)
    first = run()
    assert formats.inflate(first) == formats.inflate(installed)
    assert align.call_count == 1


@pytest.mark.parametrize('change', ['layout', 'main', 'supplement', 'codec'])
def test_alignment_cache_tracks_every_source(alignment, monkeypatch, change):
    game, run, align, _installed = alignment
    run()
    if change == 'layout':
        run(b'new layout')
    elif change == 'codec':
        monkeypatch.setattr(mod_loader, '_composition_revision', lambda: b'changed codec')
        run()
    else:
        relative = Path('menu/menu.tpf.dcx' if change == 'main' else 'menu/menu_0.tpf.dcx')
        header, rows = texture_packs.read(formats.inflate((game / relative).read_bytes()))
        from dataclasses import replace
        rows[0] = replace(rows[0], data=rows[0].data[:-1] + bytes([rows[0].data[-1] ^ 1]))
        run(files={relative: dcx(texture_packs.write(header, rows))})
    assert align.call_count == 2


@pytest.mark.parametrize('failure', ['load', 'store', 'malformed'])
def test_alignment_cache_failure_regenerates_without_failing_save(alignment, monkeypatch, failure):
    _game, run, align, installed = alignment
    if failure == 'malformed':
        monkeypatch.setattr(composition_cache, 'load', lambda *_: b'DCX\0damaged')
    else:
        monkeypatch.setattr(composition_cache, failure, Mock(side_effect=OSError('cache unavailable')))
    assert formats.inflate(run()) == formats.inflate(installed)
    assert align.call_count == 1
