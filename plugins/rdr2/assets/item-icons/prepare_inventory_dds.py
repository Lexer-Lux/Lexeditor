from pathlib import Path
from PIL import Image


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "build" / "dds"
# Power of two, and in the same range as the shipped inventory icons. Every
# texture in the dictionary is normalised to this.
ICON_SIZE = 256
TEXTURES = [
    "LEX_ICON_EMPTY_BOTTLE",
    "LEX_ICON_STEEL",
    "LEX_ICON_LEAD",
    "LEX_ICON_BRASS",
    "LEX_ICON_GUNPOWDER",
    "LEX_AMMO_225",
    "LEX_AMMO_307",
    "LEX_AMMO_444",
    "LEX_CASING_225",
    "LEX_CASING_307",
    "LEX_CASING_444",
    "LEX_CASING_REVOLVER",
    "LEX_CASING_PISTOL",
    "LEX_CASING_REPEATER",
    "LEX_CASING_RIFLE",
    "LEX_CASING_VARMINT",
    "LEX_CASING_SHOTGUN",
]


if OUTPUT.exists():
    for old_file in OUTPUT.glob("*.dds"):
        old_file.unlink()
OUTPUT.mkdir(parents=True, exist_ok=True)
for texture in TEXTURES:
    image = Image.open(ROOT / f"{texture.lower()}.png").convert("RGBA")
    # #193: the source art was written straight through at whatever size it
    # happened to be — 512x512 for the casings and 1254x1254 for the bottle and
    # the material icons. 1254 is NOT a power of two, which a DXT5 RAGE texture
    # has to be, and the whole dictionary came to 11 MB for seventeen icons.
    # Both are fixed by normalising every icon to one power-of-two size here.
    if image.size != (ICON_SIZE, ICON_SIZE):
        image = image.resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS)
    image.save(OUTPUT / f"{texture}.dds", format="DDS", pixel_format="DXT5")
print(f"Prepared {len(TEXTURES)} DDS textures at {ICON_SIZE}x{ICON_SIZE} in {OUTPUT}")
