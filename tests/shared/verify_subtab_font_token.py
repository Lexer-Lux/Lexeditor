"""A theme can give subtabs a face it can actually render bold.

The subtab bar forces weight 800 in the theme's display face. RDR2's display
face only ships weight 400, so the small labels got a synthetic bold that
smeared them. The face is now a token (--lex-subtab-font) that keeps the shared
default while letting a theme whose display face has no bold weight point the
labels at its body face instead.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    css = (ROOT / "ui" / "framework.css").read_text(encoding="utf-8")
    rdr2 = (ROOT / "plugins" / "rdr2" / "boot.js").read_text(encoding="utf-8")

    # The shared rule keeps its old default and only adds the escape hatch.
    assert "font:var(--lex-subtab-font, 800 .98em/1 var(--lex-heading-font))" in css

    # RDR2 redirects subtabs to the body face, which renders the weight it is
    # asked for, instead of the 400-only display face that was synthesised.
    assert '"subtab-font"' in rdr2
    assert '"Lex RDR Lino"' in rdr2.split('"subtab-font"')[1].split('}')[0]
    assert "Lex Redemption" not in rdr2.split('"subtab-font"')[1].split('}')[0]

    print("Subtab font token: shared default intact, RDR2 uses its body face")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
