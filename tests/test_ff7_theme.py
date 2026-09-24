"""FF7 theme: menu font pipeline, skin/sound wiring, provenance (F8)."""
import json
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from plugins.ff7 import game_font  # noqa: E402
from theme_sounds import SOUND_SLOTS, ensure_theme_sounds, sound_file  # noqa: E402
from tools.verify_ff7_completion import lgp_fixture  # noqa: E402

FF7 = ROOT / "plugins" / "ff7"


def font_member(cells: dict[int, list[tuple[int, int]]]) -> bytes:
    """A synthetic usfont_h.tex with ink pixels at cell-relative coords."""
    pixels = bytearray(256 * 256)
    for cell, points in cells.items():
        row, column = divmod(cell, game_font.ATLAS_COLUMNS)
        for dx, dy in points:
            pixels[(row * 12 + dy) * 256 + column * 12 + dx] = 3
    return (b"\0" * game_font.TEX_HEADER
            + b"\0" * game_font.TEX_PALETTES * game_font.TEX_ENTRIES * 4
            + bytes(pixels))


def test_font_pipeline_maps_cells_to_text_codes(tmp_path, monkeypatch):
    # Every printable code gets its own 2x2 ink cell; empty cells stay out.
    from plugins.ff7.format_codec import TEXT_MAP
    wanted = [code for code in range(0x01, 0xE7)
              if code < len(TEXT_MAP) and TEXT_MAP[code] != " "]
    ink = {code: [(0, 0), (1, 0), (0, 1), (1, 1)] for code in wanted}
    archive = lgp_fixture([(game_font.FONT_MEMBER, font_member(ink))])
    game = tmp_path / "game"
    member_dir = game / "ff7" / "workingdir" / "data" / "menu"
    member_dir.mkdir(parents=True)
    (member_dir / "menu_us.lgp").write_bytes(archive)
    monkeypatch.setattr(game_font, "FONT_PATH", tmp_path / "ff7-menu.ttf")
    monkeypatch.setattr(game_font, "FONT_REVISION_PATH", tmp_path / "revision")

    found = game_font.extract_glyphs(game)
    assert len(found["glyphs"]) == len({TEXT_MAP[code] for code in wanted}) + 1
    assert found["glyphs"]["T"]["box"] is not None
    assert found["glyphs"]["T"]["advance"] == 12
    assert found["glyphs"][" "]["box"] is None

    path = game_font.ensure_font(game)
    assert path.is_file()
    from fontTools.ttLib import TTFont
    names = {record.nameID: record.toUnicode()
             for record in TTFont(path)["name"].names if record.platformID == 3}
    assert names[1] == names[4] == "FF7 Menu"
    assert names[6] == "FF7Menu"


def test_font_rejects_a_truncated_member(tmp_path):
    game = tmp_path / "game"
    member_dir = game / "ff7" / "workingdir" / "data" / "menu"
    member_dir.mkdir(parents=True)
    (member_dir / "menu_us.lgp").write_bytes(
        lgp_fixture([(game_font.FONT_MEMBER, b"\0" * 100)]))
    with pytest.raises(ValueError, match="incomplete"):
        game_font.extract_glyphs(game)


def test_theme_wiring_references_each_layer():
    html = (FF7 / "editor.html").read_text(encoding="utf-8")
    assert html.index("neutral.css") < html.index('href="editor.css"')
    css = (FF7 / "editor.css").read_text(encoding="utf-8")
    assert '@font-face' in css and '"FF7 Menu"' in css
    assert "/assets/ff7-menu.ttf" in css and "--lex-skin:on" in css.replace(" ", "")
    assert "--lex-font:" in css.replace(" ", "")
    server = (FF7 / "server.py").read_text(encoding="utf-8")
    assert '"/assets/ff7-menu.ttf"' in server
    assert '"/assets/theme-sfx/"' in server
    assert "ensure_theme_sounds" in server
    editor = (FF7 / "editor.js").read_text(encoding="utf-8")
    assert "configureThemeSounds(state.dashboard.themeSounds)" in editor
    assert '"FF7 Menu"' in editor
    workspace = (FF7 / "workspace.js").read_text(encoding="utf-8")
    assert 'playThemeSound?.("move")' in workspace
    assert 'playThemeSound?.("confirm")' in workspace


def test_ff7_sound_fixture_extracts_to_slots(tmp_path):
    # The server's FF7 slot map against a four-record PCM archive.
    sound_ids = {"confirm": 1, "move": 1, "back": 4, "exit": 4,
                 "save": 2, "launch": None}
    assert set(sound_ids) <= set(SOUND_SLOTS)
    fmt, dat = bytearray(), bytearray()
    for index in range(4):
        payload = bytes([(index * 64 + sample) % 256 for sample in range(8)])
        fmt += struct.pack("<IIIIII", len(payload), 0, 0, 1, 0, 0)
        fmt += struct.pack("<HHIIHHH", 1, 1, 8000, 8000, 1, 8, 0)
        dat += payload
    game = tmp_path / "game"
    sounds = game / "ff7" / "workingdir" / "data" / "sound"
    sounds.mkdir(parents=True)
    (sounds / "audio.fmt").write_bytes(bytes(fmt))
    (sounds / "audio.dat").write_bytes(bytes(dat))
    result = ensure_theme_sounds(
        game, tmp_path / "data",
        ("data/sound", "ff7/workingdir/data/sound"), sound_ids,
        format_kind="ff7")
    assert result["ready"] is True
    by_slot = {row["slot"]: row for row in result["rows"]}
    assert by_slot["confirm"]["available"] is True
    assert by_slot["confirm"]["url"] == "/assets/theme-sfx/confirm.wav"
    assert by_slot["launch"]["available"] is False
    target = sound_file(tmp_path / "data", "confirm")
    assert target is not None and target.read_bytes()[:4] == b"RIFF"


def test_theme_provenance_is_recorded():
    sources = json.loads((ROOT / "ui" / "credits-sources.json").read_text(encoding="utf-8"))
    roles = " ".join(entry.get("role", "")
                     for entry in sources["plugins"]["ff7"]["contributions"])
    assert "usfont_h.tex" in roles
    assert "audio.fmt" in roles
    third_party = (FF7 / "THIRD_PARTY.md").read_text(encoding="utf-8")
    assert "usfont_h.tex" in third_party
    assert "never redistributed" in third_party.lower()
