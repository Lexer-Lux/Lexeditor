"""Build complete GENERIC_TEXTURES contents plus the approved casing art."""

from __future__ import annotations

import argparse
import io
import urllib.request
import zipfile
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent
PACK_URL = (
    "https://femga.com:8080/images/samples/ui_textures_no_bg/"
    "generic_textures.zip"
)
# Texture names MUST be lowercase. A RAGE texture dictionary is keyed by the
# joaat hash of the name, and every consumer (catalog UI, DRAW_SPRITE) lowercases
# the string before hashing -- which is why the catalog can say AMMO_RIFLE while
# the shipped dictionary stores `ammo_rifle`. A texture written as
# LEX_CASING_225 is filed under joaat("LEX_CASING_225") = 0x9B455FDD, while the
# game looks up joaat("lex_casing_225") = 0x3448E7D9, and the icon is blank.
# That single mistake is why three successive dictionary rebuilds (#11) changed
# nothing. See worklog/issues/github-11.md.
CUSTOM = {
    "lex_casing_225": ROOT / "lex_casing_225.png",
    "lex_casing_307": ROOT / "lex_casing_307.png",
    "lex_casing_444": ROOT / "lex_casing_444.png",
    "lex_casing_shotgun": ROOT / "lex_casing_shotgun.png",
    # Crafting materials, moved off the never-loaded LEX_INVENTORY_ITEMS
    # dictionary (probe: exists=1 loaded_before_request=0) onto this resident
    # one (probe: exists=1 loaded_before_request=1).
    "lex_icon_brass": ROOT / "lex_icon_brass.png",
    "lex_icon_gunpowder": ROOT / "lex_icon_gunpowder.png",
    "lex_icon_lead": ROOT / "lex_icon_lead.png",
    "lex_icon_steel": ROOT / "lex_icon_steel.png",
}
VANILLA_TEXTURE_COUNT = 45
SIZE = 128


def save_dds(source: Image.Image, output: Path) -> None:
    image = source.convert("RGBA")
    if image.size != (SIZE, SIZE):
        image = image.resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    image.save(output, format="DDS", pixel_format="DXT5")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", type=Path, help="cached generic_textures.zip")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    raw = args.pack.read_bytes() if args.pack else urllib.request.urlopen(PACK_URL).read()
    args.output.mkdir(parents=True, exist_ok=True)
    for old in args.output.glob("*.dds"):
        old.unlink()

    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        pngs = sorted(name for name in archive.namelist() if name.lower().endswith(".png"))
        if len(pngs) != VANILLA_TEXTURE_COUNT:
            raise RuntimeError(
                f"expected {VANILLA_TEXTURE_COUNT} Rockstar textures; found {len(pngs)}"
            )
        for name in pngs:
            texture = Path(name).stem
            with archive.open(name) as stream:
                save_dds(Image.open(stream), args.output / f"{texture}.dds")

    for texture, source in CUSTOM.items():
        save_dds(Image.open(source), args.output / f"{texture}.dds")
    print(f"Prepared {len(pngs)} Rockstar + {len(CUSTOM)} custom DDS textures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
