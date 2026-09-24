"""FF9 theme fonts: copied privately from the installed Memoria bundle."""
from __future__ import annotations

import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from plugins.ff9 import game_font, paths  # noqa: E402


def tiny_font(family: str) -> bytes:
    pen = TTGlyphPen(None)
    pen.moveTo((0, 0)); pen.lineTo((100, 0)); pen.lineTo((100, 700)); pen.lineTo((0, 700)); pen.closePath()
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder([".notdef", "A"])
    builder.setupCharacterMap({ord("A"): "A"})
    builder.setupGlyf({".notdef": TTGlyphPen(None).glyph(), "A": pen.glyph()})
    builder.setupHorizontalMetrics({".notdef": (500, 0), "A": (600, 0)})
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable({"familyName": family, "styleName": "Regular"})
    builder.setupOS2()
    builder.setupPost()
    buffer = io.BytesIO()
    builder.save(buffer)
    return buffer.getvalue()


def encrypted_bundle(*families: str) -> bytes:
    """A UnityRaw stand-in with embedded fonts, block-swapped as Memoria ships it."""
    body = b"UnityRaw" + b"\0" * 2048
    for family in families:
        # A false sfnt signature between assets must not stop the scan.
        body += b"\x00\x01\x00\x00junk" + b"\0" * 64 + tiny_font(family) + b"\0" * 32
    body += b"\0" * 1024
    return b"\xee" * 1024 + body[1024:] + body[:1024]


class FF9GameFontTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.game = self.root / "game"
        self.generated = self.root / "data" / "generated"
        patches = (mock.patch.object(paths, "GAME_ROOT", self.game),
                   mock.patch.object(game_font, "GENERATED", self.generated))
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.addCleanup(self.temp.cleanup)

    def install(self, payload: bytes) -> Path:
        bundle = self.game / "FF9_Data" / "EmbeddedAsset" / "FA" / "p_fa.mpc"
        bundle.parent.mkdir(parents=True)
        bundle.write_bytes(payload)
        return bundle

    def test_decrypt_restores_unity_raw_header(self):
        data = game_font.decrypt(encrypted_bundle("Alexandria"))
        self.assertTrue(data.startswith(b"UnityRaw"))
        with self.assertRaises(ValueError):
            game_font.decrypt(b"\0" * 4096)

    def test_extracts_both_faces_into_private_cache_once(self):
        self.install(encrypted_bundle("TBUDGothic Std B", "Alexandria", "Garnet"))
        menu = game_font.ensure_font("ff9-menu.ttf")
        heading = game_font.ensure_font("ff9-heading.ttf")
        self.assertEqual(menu.parent, self.generated)
        self.assertEqual(TTFont(menu)["name"].getDebugName(1), "Alexandria")
        self.assertEqual(TTFont(heading)["name"].getDebugName(1), "Garnet")
        stamp = menu.stat().st_mtime_ns
        with mock.patch.object(game_font, "carve_fonts", side_effect=AssertionError("re-extracted")):
            self.assertEqual(game_font.ensure_font(), menu)
        self.assertEqual(menu.stat().st_mtime_ns, stamp)

    def test_missing_install_or_face_fails_closed(self):
        with self.assertRaises(FileNotFoundError):
            game_font.ensure_font()
        self.install(encrypted_bundle("Alexandria"))
        with self.assertRaises(FileNotFoundError):
            game_font.ensure_font()
        with self.assertRaises(FileNotFoundError):
            game_font.ensure_font("../ff9-menu.ttf")
        self.assertFalse((self.generated / "ff9-menu.ttf").exists())

    def test_stylesheet_uses_the_served_faces(self):
        css = (ROOT / "plugins" / "ff9" / "editor.css").read_text(encoding="utf-8")
        for served in game_font.FACES:
            self.assertIn(f'url("/assets/{served}', css)
        server = (ROOT / "plugins" / "ff9" / "server.py").read_text(encoding="utf-8")
        self.assertIn("game_font.FACES", server)


REAL_ROOT = Path(os.environ.get("LEXEDITOR_FF9_ROOT", r"D:\SteamLibrary\steamapps\common\FINAL FANTASY IX"))


@unittest.skipUnless((REAL_ROOT / "FF9_Data" / "EmbeddedAsset" / "FA" / "p_fa.mpc").is_file(),
                     "Installed FF9 Memoria font bundle not available")
class FF9InstalledFontTests(unittest.TestCase):
    def test_installed_bundle_yields_the_theme_faces(self):
        with tempfile.TemporaryDirectory() as temp, \
                mock.patch.object(paths, "GAME_ROOT", REAL_ROOT), \
                mock.patch.object(game_font, "GENERATED", Path(temp)):
            for served, family in game_font.FACES.items():
                font = TTFont(game_font.ensure_font(served))
                self.assertEqual(font["name"].getDebugName(1), family)
                cmap = font.getBestCmap()
                for character in "ABCXYZabcxyz0123456789":
                    self.assertIn(ord(character), cmap, (family, character))


if __name__ == "__main__":
    unittest.main()
