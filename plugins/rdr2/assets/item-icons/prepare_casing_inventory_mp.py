"""Build a complete INVENTORY_ITEMS_MP DDS set plus Lexer's casing art.

The existing MP dictionary name is essential: LML registered the new
LEX_INVENTORY_ITEMS YTD, but RDR2 never completed a streamed request for it.
Replacing the existing MP dictionary makes the texture resource loadable while
keeping every Rockstar texture in that dictionary.
"""

from __future__ import annotations

import argparse
import io
import os
import urllib.request
import zipfile
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = Path(os.environ.get("LEXEDITOR_RDR2_PROJECT", r"C:\RDR2Mod")).resolve()
PACK_URL = (
    "https://femga.com:8080/images/samples/ui_textures_no_bg/"
    "ui_textures_mp/inventory_items_mp.zip"
)
RESIDENT_MAP_ICON_DDS = (
    PROJECT_ROOT / "GameplayTweaks/icons/build_resident_map_icons/dds"
)

CUSTOM = {
    "lex_recon_human": PROJECT_ROOT / "GameplayTweaks/icons/recon/lex_recon_human.png",
    "LEX_CASING_225": ROOT / "lex_casing_225.png",
    "LEX_CASING_307": ROOT / "lex_casing_307.png",
    "LEX_CASING_444": ROOT / "lex_casing_444.png",
    "LEX_CASING_SHOTGUN": ROOT / "lex_casing_shotgun.png",
    # Custom blip dictionaries never became resident in Story Mode. Keep the
    # exact inactive-campfire art in the same complete, proven resident
    # replacement as the casing icons.
    "lex_blip_campfire_inactive": (
        PROJECT_ROOT / "GameplayTweaks/icons/final/campfire-inactive.png"
    ),
    # #86: the map renderer rejected both the custom lex_blips dictionary and
    # an appended resident-blips override. INVENTORY_ITEMS_MP is the already
    # proven complete resident replacement used by the working custom inactive
    # campfire blip, so route the animal diamond through that same path.
    "lex_blip_recon_animal": (
        PROJECT_ROOT / "GameplayTweaks/icons/recon/lex_blip_recon_animal.png"
    ),
    # #153: every custom map texture uses this same proven complete resident
    # dictionary. The standalone lex_blips dictionary repeatedly rendered as
    # black quads even when requested, and adding a new icon kept regressing
    # previously working markers. Preserve the complete historical set here.
    "lex_blip_card": RESIDENT_MAP_ICON_DDS / "lex_blip_card.dds",
    "lex_blip_bone": RESIDENT_MAP_ICON_DDS / "lex_blip_bone.dds",
    "lex_blip_carving": RESIDENT_MAP_ICON_DDS / "lex_blip_carving.dds",
    "lex_blip_corpse_faint": RESIDENT_MAP_ICON_DDS / "lex_blip_corpse_faint.dds",
    "lex_blip_dreamcatcher": RESIDENT_MAP_ICON_DDS / "lex_blip_dreamcatcher.dds",
    "lex_blip_grave": RESIDENT_MAP_ICON_DDS / "lex_blip_grave.dds",
    "lex_blip_skin_faint": RESIDENT_MAP_ICON_DDS / "lex_blip_skin_faint.dds",
    "lex_blip_treasure": RESIDENT_MAP_ICON_DDS / "lex_blip_treasure.dds",
    "lex_blip_water_pump": RESIDENT_MAP_ICON_DDS / "lex_blip_water_pump.dds",
    "lex_blip_hat_bloodstain": RESIDENT_MAP_ICON_DDS / "lex_blip_hat_bloodstain.dds",
    "lex_blip_horse_drink": RESIDENT_MAP_ICON_DDS / "lex_blip_horse_drink.dds",
}
SIZE = 128


def save_dds(source: Image.Image, output: Path) -> None:
    image = source.convert("RGBA")
    if image.size != (SIZE, SIZE):
        image = image.resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    image.save(output, format="DDS", pixel_format="DXT5")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", type=Path, help="cached inventory_items_mp.zip")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    raw = args.pack.read_bytes() if args.pack else urllib.request.urlopen(PACK_URL).read()
    args.output.mkdir(parents=True, exist_ok=True)
    for old in args.output.glob("*.dds"):
        old.unlink()

    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        pngs = sorted(name for name in archive.namelist() if name.lower().endswith(".png"))
        if len(pngs) != 432:
            raise RuntimeError(f"expected 432 Rockstar MP textures; found {len(pngs)}")
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
