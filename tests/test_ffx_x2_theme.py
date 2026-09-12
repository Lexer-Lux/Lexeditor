from __future__ import annotations

from pathlib import Path

from games.ffx_x2 import theme
from games.ffx_x2.plugin import _write_fixture_vbf
from games.ffx_x2.vbf import read_index


def test_theme_cache_uses_installed_assets_without_touching_archives(tmp_path: Path):
    x_archive = tmp_path / "FFX_Data.vbf"
    meta_archive = tmp_path / "metamenu.vbf"
    png = b"\x89PNG\r\n\x1a\nSYNTHETIC-TITLE"
    _write_fixture_vbf(x_archive, [
        ("ffx_data/gamedata/ps3data/menu_us/base_ftc/d3d11/font.dds.phyre", b"FONT"),
        ("ffx_data/gamedata/ps3data/menu_us/d3d11/window.dds.phyre", b"TEXTURE"),
        ("ffx_data/gamedata/ps3data/sound_pc/menu/menu_se.fsb", b"FSB5-SFX"),
    ])
    _write_fixture_vbf(meta_archive, [
        ("metamenu/ps3data/menumetamenu/us/titlemenu.png", png),
    ])
    before_x = x_archive.read_bytes()
    before_meta = meta_archive.read_bytes()

    cache = tmp_path / "cache"
    state = theme.build(cache, {"x": read_index(x_archive)}, read_index(meta_archive))
    assert state["source"] == "installed-game"
    assert state["background"]["ready"] is True
    assert state["font"]["atlasRecognized"] == 1
    assert state["font"]["atlasCached"] == 1
    assert state["textures"]["recognized"] >= 1
    assert state["textures"]["cached"] >= 1
    assert state["sfx"]["recognizedBanks"] == 1
    assert state["sfx"]["cachedBanks"] == 1
    assert theme.asset_path(cache, state["background"]["url"].removeprefix("/theme/" )).read_bytes() == png

    # Reopening the same source generation is a cache hit and source archives stay immutable.
    assert theme.build(cache, {"x": read_index(x_archive)}, read_index(meta_archive)) == state
    assert x_archive.read_bytes() == before_x
    assert meta_archive.read_bytes() == before_meta


def test_theme_asset_route_cannot_serve_raw_cache(tmp_path: Path):
    root = tmp_path / "cache"
    raw = root / "token" / "raw" / "fonts" / "font.dds.phyre"
    raw.parent.mkdir(parents=True)
    raw.write_bytes(b"private")
    try:
        theme.asset_path(root, "token/raw/fonts/font.dds.phyre")
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("raw proprietary theme sources must not be web-served")
