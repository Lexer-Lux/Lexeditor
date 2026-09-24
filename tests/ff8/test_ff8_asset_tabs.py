"""FF8 SFX, Models, and Textures asset tabs: parsers, claims, and saves."""
import base64
import io
import json
import os
import struct
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from plugins.ff8 import assets


@pytest.fixture(autouse=True)
def _isolate_live_roots(tmp_path, monkeypatch):
    """Redirect every writable root at a scratch dir for the whole file."""
    monkeypatch.setattr(assets.paths, "PROJECT_ROOT", tmp_path / "project")
    monkeypatch.setattr(assets.paths, "DIRECT_ROOT", tmp_path / "project" / "direct")
    monkeypatch.setattr(assets.paths, "MODS_ROOT", tmp_path / "mods")


def tim_bytes(width=4, height=4, depth=8, palettes=1):
    """Build a minimal valid TIM for parser tests."""
    if depth == 4:
        flags, per_palette, pixel_bytes = 0x08, 16, (width * height + 1) // 2
    elif depth == 8:
        flags, per_palette, pixel_bytes = 0x09, 256, width * height
    else:
        flags, per_palette, pixel_bytes = 0x02, 0, width * height * 2
    out = bytearray(struct.pack("<II", 0x10, flags))
    if per_palette:
        colors = per_palette * palettes
        out += struct.pack("<IHHHH", 12 + colors * 2, 0, 0, per_palette, palettes)
        out += b"\x1f\x00" * colors
    words = width // (4 if depth == 4 else 2 if depth == 8 else 1)
    out += struct.pack("<IHHHH", 12 + pixel_bytes, 0, 0, words, height)
    out += bytes(pixel_bytes)
    return bytes(out)


def dat_bytes(sections, raw_count=None):
    """Build a model container with sections of the given sizes."""
    raw_count = len(sections) if raw_count is None else raw_count
    positions = []
    cursor = 4 + (raw_count + 1) * 4
    for size in sections:
        positions.append(cursor)
        cursor += size
    positions.append(cursor)
    out = bytearray(struct.pack("<I", raw_count))
    out += struct.pack(f"<{len(positions)}I", *positions)
    for index, size in enumerate(sections):
        out += bytes([index + 1]) * size
    return bytes(out)


def test_tim_layout_supports_4_8_and_16_bit():
    assert assets._tim_layout(tim_bytes(4, 4, 4))["depth"] == 4
    layout = assets._tim_layout(tim_bytes(8, 2, 8, palettes=3))
    assert (layout["width"], layout["height"], layout["paletteCount"]) == (8, 2, 3)
    assert assets._tim_layout(tim_bytes(4, 4, 16))["depth"] == 16


def test_tim_layout_rejects_bad_magic_truncation_and_24_bit():
    with pytest.raises(ValueError):
        assets._tim_layout(b"\x11\x00\x00\x00\x08\x00\x00\x00")
    with pytest.raises(ValueError):
        assets._tim_layout(tim_bytes()[:10])
    with pytest.raises(ValueError):
        assets._tim_layout(struct.pack("<II", 0x10, 0x03) + bytes(100))


def test_tim_png_renders_indexed_pixels():
    png = assets.tim_png_bytes(tim_bytes(4, 4, 8), 0, 0)
    image = Image.open(io.BytesIO(png))
    assert image.size == (4, 4)
    with pytest.raises(ValueError):
        assets.tim_png_bytes(tim_bytes(4, 4, 8), 0, 1)


def test_parse_dat_sections_accepts_empty_sections_and_rejects_rewinds():
    sections = assets.parse_dat_sections(dat_bytes([10, 0, 20]))
    assert [(section["index"], section["size"]) for section in sections] == [(1, 10), (2, 0), (3, 20)]
    raw = bytearray(dat_bytes([10, 10]))
    struct.pack_into("<I", raw, 8, 4)  # Second position rewinds into the header.
    assert assets.parse_dat_sections(bytes(raw)) is None
    assert assets.parse_dat_sections(b"\x01\x02\x03") is None


def test_section_names_cover_every_battle_layout():
    monster, names = assets._section_names("c0m001.dat", 11)
    assert (monster, names[-1]) == ("monster", "Textures")
    assert assets._section_names("c0m127.dat", 2)[0] == "nomodel"
    assert assets._section_names("c0m001.dat", 2)[0] == "unmapped"
    assert assets._section_names("d0c000.dat", 7)[0] == "body"
    assert assets._section_names("d7c016.dat", 10)[0] == "edea"
    assert assets._section_names("d0w003.dat", 8)[0] == "weapon"
    assert assets._section_names("d1w008.dat", 5)[0] == "weapon-reduced"
    assert assets._section_names("d0w003.dat", 5)[0] == "unmapped"
    assert assets._section_names("a0stg001.x", 4)[0] == "unmapped"


def test_geometry_counts_walk_objects_and_fail_closed():
    out = bytearray(struct.pack("<II", 1, 8))
    out += struct.pack("<H", 1)  # One vertex group.
    out += struct.pack("<HH", 3, 2) + bytes(12)  # Bone 3, two vertices.
    out += b"\x00" * ((4 - len(out) % 4) % 4)
    out += struct.pack("<HHHHI", 2, 1, 0, 0, 0)
    out += bytes(2 * 16 + 1 * 20)
    out += struct.pack("<I", 2)
    counts = assets._geometry_counts(bytes(out), {"offset": 0, "size": len(out)})
    assert counts == {"objects": 1, "vertices": 2, "triangles": 2, "quads": 1}
    assert assets._geometry_counts(bytes(out[:-1]), {"offset": 0, "size": len(out) - 1}) is None


def test_texture_layouts_skips_empty_slots_and_rejects_bad_tims():
    empty_section = struct.pack("<I", 2) + struct.pack("<III", 16, 16, 16)
    assert assets._texture_layouts(empty_section, {"offset": 0, "size": 16}) == []
    good = tim_bytes(4, 4, 4)
    head = struct.pack("<I", 2) + struct.pack("<III", 16, 16 + len(good), 16 + len(good))
    data = head + good
    layouts = assets._texture_layouts(data, {"offset": 0, "size": len(data)})
    assert [(layout["index"], layout["depth"]) for layout in layouts] == [(0, 4)]
    broken = head + b"\x00" * len(good)
    assert assets._texture_layouts(broken, {"offset": 0, "size": len(broken)}) is None


def test_sfx_claim_id_maps_ffnx_names():
    fields = {"balamb1", "delin1"}
    assert assets._sfx_claim_id("5", fields) == (5, None, True)
    assert assets._sfx_claim_id("battle_9", fields) == (9, "battle", True)
    assert assets._sfx_claim_id("menu_3", fields) == (3, "menu", True)
    assert assets._sfx_claim_id("world_12", fields) == (12, "world", True)
    assert assets._sfx_claim_id("balamb1_7", fields) == (7, "balamb1", True)
    assert assets._sfx_claim_id("delin1_4_11", fields) == (11, "delin1_4", True)
    assert assets._sfx_claim_id("unknown_7", fields) == (None, None, False)
    assert assets._sfx_claim_id("boss", fields) == (None, None, False)
    assert assets._sfx_claim_id("battle_x", fields) == (None, None, False)


def test_texture_claim_extends_only_verified_bases():
    stems = {"c0m001", "d0c000"}
    assert assets._texture_claim("battle/c0m001.dat_0.png", stems, 20)[0] == "model:c0m001.dat"
    assert assets._texture_claim("battle/d0c000_1.png", stems, 20)[0] == "model:d0c000.dat"
    assert assets._texture_claim("world/dat/texl/texture3_0.png", stems, 20)[0] == "texl:3"
    assert assets._texture_claim("world/dat/texl/texture30.png", stems, 20)[0].startswith("file:")
    assert assets._texture_claim("battle/c0m00.dat_0.png", stems, 20)[0].startswith("file:")
    assert assets._texture_claim("cardgame/custom.png", stems, 20)[0].startswith("file:")


def fake_entries(count=10):
    entries = []
    for index in range(count):
        entries.append({"length": 1024 if index else 0, "offset": index * 1024,
                        "flags": 1 if index == 3 else 0, "tag": 2, "channels": 1,
                        "rate": 44100, "average": 0, "alignment": 1024,
                        "bits": 4, "format": b"\x00" * 18,
                        "extra": struct.pack("<HH", 1016, 7) + bytes(28)})
    return entries


def test_sfx_rows_attribute_mod_files_and_flag_placeholders(tmp_path):
    sfx = tmp_path / "sfx"
    sfx.mkdir()
    (sfx / "5.ogg").write_bytes(b"OggS" + bytes(100))
    (sfx / "battle_9.ogg").write_bytes(b"OggS" + bytes(100))
    (sfx / "notes.txt").write_text("not audio")
    (sfx / "config.toml").write_text("[5]\nloop = true\n")
    with patch.object(assets.paths, "PROJECT_ROOT", tmp_path), \
            patch.object(assets, "_sfx_entries", return_value=fake_entries()), \
            patch.object(assets, "_field_names", return_value=set()), \
            patch.object(assets, "_external_sfx_enabled", return_value=True):
        payload = assets.sfx_rows("current")
    rows = {str(row["id"]): row for row in payload["rows"]}
    assert [entry["file"] for entry in rows["5"]["modFiles"]] == ["5.ogg"]
    assert rows["5"]["config"] == {"loop": True}
    assert [entry["file"] for entry in rows["9"]["modFiles"]] == ["battle_9.ogg"]
    assert rows["0"]["valid"] is False and rows["0"]["note"]
    assert rows["file:notes.txt"]["valid"] is False
    assert payload["externalSfx"] is True


def test_save_sfx_round_trip_and_revert(tmp_path):
    data = b"OggS" + bytes(200)
    with patch.object(assets.paths, "PROJECT_ROOT", tmp_path), \
            patch.object(assets, "_sfx_entries", return_value=fake_entries()):
        assert assets.save_sfx([{"id": 5, "audioBase64": base64.b64encode(data).decode(),
                                          "ext": "ogg"}]) == {"saved": 1}
        assert (tmp_path / "sfx" / "5.ogg").read_bytes() == data
        assert assets.save_sfx([{"id": 5, "revert": True}]) == {"saved": 1}
        assert not (tmp_path / "sfx" / "5.ogg").exists()
        with pytest.raises(ValueError):
            assets.save_sfx([{"id": 99, "revert": True}])
        with pytest.raises(ValueError):
            assets.save_sfx([{"id": 5, "audioBase64": base64.b64encode(b"RIFF").decode(),
                                        "ext": "ogg"}])
        with pytest.raises(ValueError):
            assets.save_sfx([{"id": 5, "audioBase64": base64.b64encode(data).decode(),
                                        "ext": "xm"}])


def test_save_models_validates_containers_and_reverts(tmp_path):
    data = dat_bytes([64] * 11)
    with patch.object(assets.paths, "PROJECT_ROOT", tmp_path), \
            patch.object(assets.paths, "DIRECT_ROOT", tmp_path / "direct"):
        assert assets.save_models([{"file": "c0m001.dat",
                                    "datBase64": base64.b64encode(data).decode()}]) == {"saved": 1}
        assert (tmp_path / "direct" / "battle" / "c0m001.dat").read_bytes() == data
        with pytest.raises(ValueError):
            assets.save_models([{"file": "c0m002.dat",
                                 "datBase64": base64.b64encode(b"junk").decode()}])
        with pytest.raises(ValueError):
            assets.save_models([{"file": "../evil.dat", "revert": True}])
        assert assets.save_models([{"file": "c0m001.dat", "revert": True}]) == {"saved": 1}
        assert not (tmp_path / "direct" / "battle" / "c0m001.dat").exists()


@pytest.fixture
def installed_game():
    fmt = Path(os.environ["LOCALAPPDATA"]) / "Lexeditor" / "game-data" / "ff8"
    game = assets.paths.GAME_ROOT / "Data" / "Sound" / "audio.fmt"
    if not game.is_file() or not (fmt / "baseline" / "en" / "battle" / "c0m001.dat").is_file():
        pytest.skip("Requires an installed FF8 game and extracted baseline")
    return fmt


def test_ensure_character_models_needs_no_game(tmp_path):
    with patch.object(assets.paths, "GAME_ROOT", tmp_path / "missing"), \
            patch.object(assets.paths, "BASELINE_ROOT", tmp_path / "baseline"):
        assert assets.ensure_character_models() == 0


def test_retail_audio_archive_matches_documented_facts(installed_game):
    payload = assets.sfx_rows("vanilla")
    assert len(payload["rows"]) == 2791
    assert sum(1 for row in payload["rows"] if row["valid"]) == 1544
    assert payload["rows"][158]["usedBy"] == ["Squall - battle slot 0"]


def test_retail_monster_model_decodes(installed_game):
    rows = {row["id"]: row for row in assets.model_rows("vanilla")["rows"]}
    gim = rows["c0m001.dat"]
    assert (gim["name"], gim["modelKind"], gim["enemyId"]) == ("GIM52A", "monster", 1)
    assert [section["name"] for section in gim["sections"]][6] == "Information & stats"
    assert gim["counts"]["vertices"] > 0 and len(gim["tims"]) == 3
    assert rows["c0m127.dat"]["modelKind"] == "nomodel"
    assert rows["d0c000.dat"]["modelKind"] == "body"
    assert rows["a0stg001.x"]["modelKind"] == "locked"


def test_retail_texture_inventory_links_models(installed_game):
    rows = assets.texture_rows("vanilla")["rows"]
    assert sum(1 for row in rows if row["id"].startswith("texl/")) == 20
    gim = [row for row in rows if row["id"] == "battle/c0m001.dat#0"][0]
    assert gim["modelFile"] == "c0m001.dat" and gim["editor"] == "models"
    png = assets.texture_png_bytes("battle/c0m001.dat#0", 0, "vanilla")
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
