"""Static, binary, and rendered-host contract for Lexeditor issue 35."""

from __future__ import annotations

import hashlib
from pathlib import Path

from fontTools.ttLib import TTFont


ROOT = Path(__file__).resolve().parents[1]
FONT = ROOT / "ui" / "assets" / "fonts" / "Lexend-Variable.ttf"
EXPECTED_SHA256 = "3add53e641fbc81da64da4bb254285e2831b52b029527bc0714e2b9610832ee6"


def main() -> int:
    assert FONT.is_file() and FONT.stat().st_size == 175_756
    assert hashlib.sha256(FONT.read_bytes()).hexdigest() == EXPECTED_SHA256

    font = TTFont(FONT)
    names = {
        record.nameID: record.toUnicode()
        for record in font["name"].names
        if record.nameID in {1, 2, 5, 6}
    }
    assert names == {
        1: "Lexend", 2: "Regular", 5: "Version 1.007", 6: "Lexend-Regular",
    }
    axes = [(axis.axisTag, axis.minValue, axis.defaultValue, axis.maxValue)
            for axis in font["fvar"].axes]
    assert axes == [("wght", 100.0, 400.0, 900.0)]

    css = (ROOT / "ui" / "framework.css").read_text(encoding="utf-8")
    chooser = (ROOT / "ui" / "chooser.html").read_text(encoding="utf-8")
    source = (FONT.parent / "SOURCE.md").read_text(encoding="utf-8")
    license_text = (FONT.parent / "OFL.txt").read_text(encoding="utf-8")
    host = (ROOT / "desktop_host.py").read_text(encoding="utf-8")

    assert '@font-face' in css and 'font-family: "Lexend"' in css
    assert 'url("assets/fonts/Lexend-Variable.ttf")' in css
    assert '--lex-font: "Lexend", "Segoe UI", system-ui, sans-serif' in css
    assert '--lex-heading-font: "Lexend", "Segoe UI", system-ui, sans-serif' in css
    assert "Segoe UI Variable Text" not in chooser
    assert "Segoe UI Variable Display" not in chooser
    assert EXPECTED_SHA256.upper() in source
    assert "e2332cf862ac3145c0ee5f24f04f4c1819b2410b" in source
    assert "20491885ca2cf7ffc556432973e7bdbc701952b5" in source
    assert "SIL OPEN FONT LICENSE Version 1.1" in license_text

    # The standard hidden WebView2 host smoke must inspect the real loaded face,
    # not only the computed fallback list.
    assert "lexendFaceLoaded" in host
    assert "face.family.replace" in host and "face.status === 'loaded'" in host
    assert 'bodyFont"].startswith("Lexend")' in host
    assert 'headingFont"].startswith("Lexend")' in host

    # Every current game skin explicitly replaces the neutral typography.
    ff8 = (ROOT / "games" / "ff8" / "editor.html").read_text(encoding="utf-8")
    rdr = (ROOT / "games" / "rdr" / "editor.html").read_text(encoding="utf-8")
    warband = (ROOT / "games" / "warband" / "editor.html").read_text(encoding="utf-8")
    rdr2 = (ROOT / "games" / "rdr2" / "editor.html").read_text(encoding="utf-8")
    assert '--lex-font:"FF8 Menu"' in ff8
    assert "--lex-font:RDRLino" in rdr
    assert '--lex-font:"Segoe UI"' in warband
    assert 'font:\'"Lex RDR Lino"' in rdr2

    print("Lexend source, license, binary, neutral defaults, and WebView2 contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
