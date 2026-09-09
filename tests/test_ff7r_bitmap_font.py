import io
import struct

import pytest
from PIL import Image

from games.ff7r import bitmap_font


def _glyph_payload(*, head=bitmap_font.GLYPH_HEAD2):
    rows = [
        # code, page, x, y, width, height, x offset, y offset, advance
        (ord("A"), 1, 10, 20, 24, 30, -1, 3, 25),
        (ord("B"), 1, 40, 20, 23, 30, 0, 3, 24),
        (ord("Z"), 2, 70, 20, 22, 30, 0, 3, 23),
    ]
    payload = bytearray(head)
    payload += struct.pack("<II", 0, len(rows))
    for row in rows:
        payload += struct.pack("<6H2hH", *row)
    if head == bitmap_font.GLYPH_HEAD:
        payload += b"\0\0\0\0"
        payload += struct.pack("<I", 1)
        payload += struct.pack("<I", 5) + b"TEST\0" + b"\0\xe0"
    payload += struct.pack("<II", 48, 2)
    payload += b"\0\0\0\0"
    payload += bitmap_font.UNREAL_TAG
    return bytes(payload)


def test_parse_glyph_uexp_reads_documented_page_one_metrics():
    parsed = bitmap_font.parse_glyph_uexp(_glyph_payload())

    assert parsed["fontSize"] == 48
    assert parsed["outline"] == 2
    assert parsed["page"] == 1
    assert parsed["glyphCount"] == 2
    assert parsed["glyphs"] == [
        {
            "codepoint": ord("A"), "page": 1, "x": 10, "y": 20,
            "width": 24, "height": 30, "xOffset": -1, "yOffset": 3,
            "xAdvance": 25,
        },
        {
            "codepoint": ord("B"), "page": 1, "x": 40, "y": 20,
            "width": 23, "height": 30, "xOffset": 0, "yOffset": 3,
            "xAdvance": 24,
        },
    ]


def test_parse_glyph_uexp_supports_documented_0109_metadata_variant():
    parsed = bitmap_font.parse_glyph_uexp(_glyph_payload(head=bitmap_font.GLYPH_HEAD))
    assert parsed["glyphCount"] == 2
    assert parsed["fontSize"] == 48


def test_parse_glyph_uexp_fails_closed_on_bad_footer_and_out_of_bounds_glyph():
    bad_footer = _glyph_payload()[:-4] + b"NOPE"
    with pytest.raises(ValueError, match="footer/length"):
        bitmap_font.parse_glyph_uexp(bad_footer)

    payload = bytearray(bitmap_font.GLYPH_HEAD2)
    payload += struct.pack("<II", 0, 1)
    payload += struct.pack("<6H2hH", ord("A"), 1, 2040, 10, 20, 20, 0, 0, 20)
    payload += struct.pack("<II", 48, 2) + b"\0\0\0\0" + bitmap_font.UNREAL_TAG
    with pytest.raises(ValueError, match="outside"):
        bitmap_font.parse_glyph_uexp(bytes(payload))


def test_atlas_layout_matches_documented_2048_bc5_mip_chain():
    assert len(bitmap_font.ATLAS_MIP_SIZES) == 12
    assert sum(bitmap_font.ATLAS_MIP_SIZES) == bitmap_font.ATLAS_RAW_SIZE
    assert (
        bitmap_font.ATLAS_HEADER_SIZE
        + bitmap_font.ATLAS_RAW_SIZE
        + bitmap_font.ATLAS_FOOTER_SIZE
        == bitmap_font.ATLAS_UEXP_SIZE
    )
    with pytest.raises(ValueError, match="font atlas size"):
        bitmap_font.decode_font_atlas_png(b"too small")


def test_pinned_texfury_decodes_documented_bc5_atlas_shape_to_png():
    # Zero BC5 blocks are valid compressed blocks. This exercises the pinned
    # texfury/Pillow production path without committing a proprietary atlas.
    payload = bytearray(bitmap_font.ATLAS_UEXP_SIZE)
    payload[-4:] = bitmap_font.UNREAL_TAG

    png = bitmap_font.decode_font_atlas_png(bytes(payload))

    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    image = Image.open(io.BytesIO(png))
    assert image.mode == "RGBA"
    assert image.size == (bitmap_font.ATLAS_WIDTH, bitmap_font.ATLAS_HEIGHT)


def test_installed_font_pipeline_caches_only_decoded_private_assets(tmp_path, monkeypatch):
    game = tmp_path / "game"
    paks = game / "End" / "Content" / "Paks"
    paks.mkdir(parents=True)
    pak = paks / "pakchunk0_s00-WindowsNoEditor.pak"
    pak.write_bytes(b"fixture")
    data = tmp_path / "data"
    glyph_path = bitmap_font.GLYPH_SUFFIXES[0]
    atlas_path = bitmap_font.ATLAS_SUFFIX

    monkeypatch.setattr(bitmap_font, "installed_paks", lambda _root: [pak])
    monkeypatch.setattr(
        bitmap_font,
        "get_file",
        lambda _pak, internal: _glyph_payload() if internal == glyph_path else b"cooked-atlas",
    )
    monkeypatch.setattr(bitmap_font, "decode_font_atlas_png", lambda payload: b"\x89PNG\r\nfixture")

    result = bitmap_font.ensure_installed_bitmap_font(game, data, [glyph_path, atlas_path])

    assert result["available"] is True
    assert result["sourceFound"] is True
    assert result["atlasUrl"] == "/theme-assets/font-atlas.png"
    assert result["glyphCount"] == 2
    assert (data / "theme-assets" / "font-atlas.png").read_bytes() == b"\x89PNG\r\nfixture"
    assert not any(path.suffix in {".uasset", ".uexp", ".ubulk"} for path in data.rglob("*"))

    # A matching PAK signature is a real cache hit: no game payload must be read again.
    monkeypatch.setattr(bitmap_font, "get_file", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("cache miss")))
    cached = bitmap_font.ensure_installed_bitmap_font(game, data, [glyph_path, atlas_path])
    assert cached["available"] is True
    assert cached["glyphCount"] == 2


def test_font_source_selection_prefers_documented_path_and_fails_on_ambiguous_ownership():
    exact = bitmap_font.GLYPH_SUFFIXES[0]
    assert bitmap_font._choose_suffix([exact, exact], (exact,)) == exact

    ambiguous = bitmap_font._choose_suffix(
        [
            "A/" + exact,
            "B/" + exact,
        ],
        (exact,),
    )
    assert ambiguous is None
