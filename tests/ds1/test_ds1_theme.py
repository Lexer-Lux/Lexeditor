"""DS1 installed-game theme: title art, fonts, sounds, palette, provenance."""
import json
import re
import struct
import sys
import zlib
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import css_audit  # noqa: E402
from plugins.ds1 import theme  # noqa: E402
from plugins.ds1.assets import render_png  # noqa: E402
from plugins.ds1.plugin import DS1Session  # noqa: E402

DS1 = ROOT / "plugins" / "ds1"


def dds_block(color0=0xF800, color1=0x001F):
    """A 4x4 single-block DXT1 texture: red by default, blue on request."""
    header = bytearray(128)
    header[0:4] = b"DDS "
    struct.pack_into("<I", header, 4, 124)
    struct.pack_into("<II", header, 12, 4, 4)
    struct.pack_into("<I", header, 76, 32)
    struct.pack_into("<I", header, 80, 0x4)
    header[84:88] = b"DXT1"
    struct.pack_into("<I", header, 108, 0x1000)
    return bytes(header) + struct.pack("<HHI", color0, color1, 0)


def tpf(entries):
    """A minimal TPF pack from (name, dds-blob) pairs."""
    table = bytearray(b"TPF\0" + b"\0" * 4 + struct.pack("<I", len(entries)) + b"\0" * 4)
    offset = 16 + len(entries) * 20
    names = [name.encode("shift_jis") + b"\0" for name, _blob in entries]
    cursor, name_cursor = offset, offset + sum(len(blob) for _name, blob in entries)
    for index, (name, blob) in enumerate(entries):
        table += struct.pack("<5I", cursor, len(blob), 0, name_cursor, 0)
        cursor += len(blob)
        name_cursor += len(names[index])
    return bytes(table) + b"".join(blob for _name, blob in entries) + b"".join(names)


def dcx(plain):
    """A DFLT DCX wrapper shaped like the installed menu pack."""
    header = bytearray(76)
    header[0:4] = b"DCX\0"
    header[4:24] = bytes.fromhex("000100000000001800000024000000240000002c")
    header[24:28] = b"DCS\0"
    header[36:40] = b"DCP\0"
    header[40:44] = b"DFLT"
    header[68:76] = b"DCA\0\0\0\0\x08"
    compressed = zlib.compress(bytes(plain), 9)
    struct.pack_into(">II", header, 28, len(plain), len(compressed))
    return bytes(header) + compressed


def fsb(names):
    """An FSB4 bank with one 80-byte sample header per name."""
    data = bytearray(struct.pack("<4sIII", b"FSB4", len(names), 0, 0) + bytes(32))
    for name in names:
        encoded = name.encode("ascii")[:29]
        data += struct.pack("<H", 80) + encoded + bytes(30 - len(encoded)) + bytes(48)
    return bytes(data)


def game_root(tmp_path):
    """A synthetic install: menu pack, font sources, one sound bank."""
    game = tmp_path / "game"
    pack = tpf([("Title", dds_block()), ("Menu14", dds_block())])
    menu = game / "menu" / "ENGLISH"
    menu.mkdir(parents=True)
    (menu / "menu_local.tpf.dcx").write_bytes(dcx(pack))
    font = game / "font" / "english"
    font.mkdir(parents=True)
    (font / "DSFont24.ccm.dcx").write_bytes(b"FONT-CONFIG")
    (font / "TalkFont24.ccm.dcx").write_bytes(b"TALK-CONFIG")
    (font / "glyphs.fnt").write_bytes(b"FONT-ATLAS")
    sound = game / "sound"
    sound.mkdir(parents=True)
    (sound / "frpg_sm17.fsb").write_bytes(fsb(["m170000000.wav", "o7230.wav", "silen.wav"]))
    (sound / "frpg_sm17.fev").write_bytes(b"FEV-PROJECT")
    return game


def snapshot(game):
    return {path.relative_to(game).as_posix(): path.read_bytes()
            for path in sorted(game.rglob("*")) if path.is_file()}


def test_theme_builds_from_installed_game_without_touching_it(tmp_path):
    game = game_root(tmp_path)
    before = snapshot(game)
    cache = tmp_path / "cache"
    state = theme.build(cache, game)
    assert state["source"] == "installed-game"
    assert state["title"]["ready"] is True
    assert state["title"]["archivePath"] == "menu/ENGLISH/menu_local.tpf.dcx"
    assert state["title"]["format"] == "DXT1"
    served = theme.asset_path(cache, state["title"]["url"].removeprefix("/theme/")).read_bytes()
    assert served == render_png(dds_block())
    assert state["font"]["recognized"] == 3
    assert state["font"]["cached"] == 3
    assert state["font"]["webReady"] is False
    assert state["sfx"]["recognizedBanks"] == 1
    assert state["sfx"]["streams"] == 3
    assert state["sfx"]["cachedProjects"] == 1
    assert state["sfx"]["webReady"] is False

    # Reopening the same install is a cache hit and sources stay immutable.
    assert theme.build(cache, game) == state
    assert snapshot(game) == before


def test_theme_without_game_is_editor_safe(tmp_path):
    for root in (None, tmp_path / "missing"):
        state = theme.build(tmp_path / "cache", root)
        assert state["source"] == "fallback"
        assert state["title"]["ready"] is False
        assert state["font"]["webReady"] is False
        assert state["sfx"]["webReady"] is False


def test_theme_prefers_the_english_menu_pack(tmp_path):
    game = game_root(tmp_path)
    french = game / "menu" / "FRENCH"
    french.mkdir(parents=True)
    (french / "menu_local.tpf.dcx").write_bytes(dcx(tpf([("Title", dds_block(0x001F, 0xF800))])))
    state = theme.build(tmp_path / "cache", game)
    assert state["title"]["archivePath"] == "menu/ENGLISH/menu_local.tpf.dcx"
    served = theme.asset_path(tmp_path / "cache", state["title"]["url"].removeprefix("/theme/")).read_bytes()
    assert served == render_png(dds_block())


def test_theme_survives_a_corrupt_menu_pack(tmp_path):
    game = game_root(tmp_path)
    (game / "menu" / "ENGLISH" / "menu_local.tpf.dcx").write_bytes(b"not a pack")
    state = theme.build(tmp_path / "cache", game)
    assert state["title"]["ready"] is False
    assert "note" in state["title"]
    assert state["font"]["cached"] == 3
    assert state["sfx"]["streams"] == 3


def test_theme_bounds_oversized_and_unproven_sources(tmp_path, monkeypatch):
    game = game_root(tmp_path)
    (game / "font" / "english" / "huge.fnt").write_bytes(b"x" * 1024)
    (game / "sound" / "frpg_sm99.fsb").write_bytes(b"not a bank")
    monkeypatch.setattr(theme, "MAX_RAW_FONT", 16)
    monkeypatch.setattr(theme, "MAX_MENU_PACK", 32)
    state = theme.build(tmp_path / "cache", game)
    assert state["title"]["ready"] is False
    assert state["font"]["recognized"] == 4
    assert state["font"]["cached"] == 3
    banks = {bank["name"]: bank for bank in state["sfx"]["banks"]}
    assert banks["frpg_sm99.fsb"]["streams"] is None
    assert state["sfx"]["streams"] == 3


def test_theme_asset_route_serves_browser_files_only(tmp_path):
    root = tmp_path / "cache"
    raw = root / "token" / "raw" / "fonts" / "DSFont24.ccm.dcx"
    raw.parent.mkdir(parents=True)
    raw.write_bytes(b"private")
    for route in ("token/raw/fonts/DSFont24.ccm.dcx", "token/../escape.png",
                  "token/browser/missing.png", ""):
        try:
            theme.asset_path(root, route)
        except FileNotFoundError:
            pass
        else:
            raise AssertionError(f"theme route served {route!r}")


def test_theme_serves_over_http(tmp_path):
    game = game_root(tmp_path)
    cache = tmp_path / "cache"
    session = DS1Session({"LEXEDITOR_DS1_ROOT": str(game),
                          "LEXEDITOR_DS1_THEME_CACHE": str(cache),
                          "LEXEDITOR_NO_MOD": "1"})
    try:
        assert session.start()["pluginId"] == "ds1"
        with urlopen(session.url.rstrip("/") + "/api/theme") as reply:
            state = json.loads(reply.read().decode("utf-8"))
        assert state["title"]["ready"] is True
        with urlopen(session.url.rstrip("/") + state["title"]["url"]) as reply:
            assert reply.read() == render_png(dds_block())
    finally:
        session.stop()
        assert session.wait_closed()


def test_palette_keeps_light_text_on_dark():
    """Headers keep light lettering on the abyss blacks.

    The shared header fg falls back to --lex-highlight and its bg to
    --lex-panel-2, so resolve the theme's variables exactly that way and
    require strong contrast.
    """
    css = (DS1 / "editor.css").read_text(encoding="utf-8")
    variables = dict(re.findall(r"--([\w-]+)\s*:\s*([^;{}]+);", css))

    def resolve(name, fallback):
        value = (variables.get(name) or variables.get(fallback) or "").strip()
        assert re.fullmatch(r"#[0-9a-fA-F]{3}([0-9a-fA-F]{3})?", value or ""), (
            "cannot contrast-check non-hex " + name)
        return value

    def luminance(hexcode):
        hexcode = hexcode.lstrip("#")
        if len(hexcode) == 3:
            hexcode = "".join(char * 2 for char in hexcode)
        levels = [int(hexcode[index:index + 2], 16) / 255 for index in (0, 2, 4)]
        linear = [channel / 12.92 if channel <= 0.03928
                  else ((channel + 0.055) / 1.055) ** 2.4 for channel in levels]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    def contrast(first, second):
        light, dark = sorted((luminance(first), luminance(second)), reverse=True)
        return (light + 0.05) / (dark + 0.05)

    pairs = ((resolve("lex-list-header-fg", "lex-highlight"),
              resolve("lex-list-header-bg", "lex-panel-2")),
             (resolve("lex-sort-header-fg", "lex-highlight"),
              resolve("lex-sort-header-bg", "lex-panel-2")))
    for foreground, background in pairs:
        assert contrast(foreground, background) >= 7, (foreground, background)
    accent = json.loads((DS1 / "plugin.json").read_text(encoding="utf-8"))["accent"]
    assert variables["lex-accent"] == accent
    assert '"Palatino Linotype"' in css
    summary = css_audit.summary()["ds1"]
    assert summary["rules"] == 0
    assert summary["important"] == 0


def test_theme_wiring_references_each_layer():
    server = (DS1 / "server.py").read_text(encoding="utf-8")
    assert "'/api/theme'" in server
    assert '"/theme/"' in server
    assert "theme_status" in server
    assert "theme.build" in server
    editor = (DS1 / "editor.js").read_text(encoding="utf-8")
    assert 'themeName:"ds1"' in editor
    assert '"accent-text":"#141210"' in editor
    assert "theme:installed-game" in (DS1 / "data_map.py").read_text(encoding="utf-8")
    assert '"theme.py"' in (DS1 / "plugin.py").read_text(encoding="utf-8")


def test_theme_provenance_is_recorded():
    credits = (DS1 / "credits.md").read_text(encoding="utf-8")
    assert "menu_local.tpf.dcx" in credits
    assert "DSFont24" in credits
    assert "frpg_sm" in credits
    assert "never redistributed" in credits.lower()
    sources = json.loads((ROOT / "ui" / "credits-sources.json").read_text(encoding="utf-8"))
    roles = " ".join(entry.get("role", "")
                     for entry in sources["plugins"]["ds1"]["contributions"])
    assert "menu_local.tpf.dcx" in roles
    assert "DSFont24" in roles
    assert "frpg_sm" in roles
