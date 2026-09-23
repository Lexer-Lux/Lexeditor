"""Truthful Steam data-map coverage for the fresh Chrono Trigger plugin."""
from __future__ import annotations

from .project import OverlayStore


ROWS = [
    ("resources.bin", "Steam resource archive", "Read-only source container. Lexeditor reads ARC1 entries but never rewrites the installed archive.", "partial", "info"),
    ("Localize/<lang>/msg/*.txt", "Dialogue, menu and item text", "Edit keyed UTF-8 text records and save only the selected resource into the mod project.", "integrated", "text"),
    ("Game/common/MapJumpOffsetTbl.dat + MapJumpDataTbl.dat", "Area exits", "Edit existing Steam 8-byte exit records: trigger tile/size, destination, facing and destination position. Counts remain unchanged.", "integrated", "exits"),
    ("Game/common/TakaraOffsetTbl.dat + TakaraDataTbl.dat", "Treasure chests", "Edit existing Steam 6-byte treasure records for position and known item/gold contents. Alias sentinels and unknown trailing words are preserved.", "integrated", "treasure"),
    ("Game/field/Mapinfo/mapinfo_*.dat", "Area settings", "Edit the fixed 24-byte current-PC area header: music and map/tileset/palette/script references plus the camera scroll mask. The unmodelled PC word and any trailing bytes are preserved.", "integrated", "scenes"),
    ("Game/field/atel/Atel_*.dat", "Events and cutscenes", "Public tools document substantial script structure, but variable command boundaries and safe resizing make this a later editor rather than part of the low-cost first slice.", "not-integrated", None),
    ("Game/field/BGSetTable/bgsettable_*.dat", "Tileset graphics sets", "Edit the eight fixed current-PC graphics-set references used by layer 1/2 tilesets. 255 remains the game's unused-slot sentinel and trailing bytes are preserved.", "integrated", "tilesets"),
    ("Game/field/ChipTable/ChipTable_*.dat + ChipTableBg3_*.dat", "Tile assemblies", "Edit fixed current-PC tile corners: chip index, palette, flips and priority. L1/L2 has 512 tiles and L3 has 256; unknown priority-byte bits and trailing bytes are preserved.", "integrated", "assemblies"),
    ("Game/field/MapTable/MapTable_*.dat", "Area map tiles", "Edit the existing fixed current-PC layer tile bytes using map coordinates and layer identity. Layer 1/2 edits stay within each tile's existing 0-255 or 256-511 bank; the six-byte map header and RLE property layout are preserved.", "integrated", "scenemaps"),
    ("Game/field/MapTable/MapTable_*.dat header", "Area render settings", "Edit the documented fixed scroll-speed nibbles, all screen-mask bits and known effect-mask bits. Map dimensions, layer-3 enable/scroll-mode bits and the unknown effect bit are preserved.", "integrated", "scenerender"),
    ("Game/field/MapTable/MapTable_*.dat RLE properties", "Area collision and movement", "Edit existing RLE property runs in place: tile-bank flags, documented collision shape, movement direction/speed, door/NPC collision, Z behavior and sprite priority. Compression state, repeat counts and the two unknown property bits are preserved.", "integrated", "sceneprops"),
    ("Game/field/PrioMap + map_bin + weather_bin", "Area priority bytes and graphics", "The PC priority bytes remain unmodelled and raster chip graphics do not yet have a safe format-specific image editor.", "not-integrated", None),
    ("Game/field/BGAnime/bganimeinfo_*.dat", "Animated map tiles", "Edit existing current-PC chip-animation destination/source chip offsets and documented frame-duration high nibbles without changing animation/frame counts. Unknown duration low nibbles, terminators and trailing bytes are preserved.", "integrated", "animations"),
    ("Game/field/palette_bin/plt*.bin + Game/world/plt_bin/plt*.bin", "Area and world palettes", "Edit the 256 RGB555 colors in current-PC field and world palettes. The two-byte prefix, bit 15 of every color, and trailing bytes are preserved.", "integrated", "palettes"),
    ("Game/common/bankc6.bin @ 0xFD10", "World settings", "Edit the seven active fixed 23-byte Steam world headers. Graphics, palette, map, music, exit and script references are bounded to one byte; the PC-unused palette-animation byte and all bytes outside the selected header are preserved.", "integrated", "worlds"),
    ("Game/world/Map/Map_*.dat", "World map tiles", "Edit the two stored fixed 96x64 current-PC tile layers. Layer 1 stays in tile range 0-255 and layer 2 in 256-511; file shape and trailing bytes are preserved.", "integrated", "worldmaps"),
    ("Game/world/Id/Id_*.dat", "World tile properties", "Edit the four documented per-chip property nibbles for each of the 256 layer-2 tiles. Unknown existing nibble values are preserved unless explicitly replaced by a documented 0-4 code.", "integrated", "worldprops"),
    ("Game/world/SeId/SeId_*.dat", "World music transitions", "Edit the two 4-bit music indexes stored in each fixed transition byte. File shape and trailing bytes are preserved.", "integrated", "worldmusic"),
    ("Game/world/colanim_bin/*_colanim.bin", "World palette-animation colors", "Edit existing flat RGB555 world animation colors. Bit 15 and any odd trailing byte are preserved.", "integrated", "worldcolors"),
    ("Game/world/EventTable/EventTable_*.dat", "World exits and triggers", "Edit existing current-PC 8-byte exits and live 3-byte triggers without changing counts. Scripted-vs-destination semantics, trigger terminators, the unknown third block, script addresses, unmodelled flag bits and trailing bytes are preserved.", "integrated", "worldnav"),
    ("Game/world/esl/Event_*.dat + map_bin + Chip + gif", "World scripts and graphics", "Current-PC world scripts and raw graphics are recognized, but this replacement does not rewrite variable script bodies or expose a raster graphics editor.", "not-integrated", None),
    ("Game/chara/dat/c*.dat", "Sprite descriptors", "Edit documented current-PC sprite size-group bits, primary-enemy flag, animation-set index and enemy hand coordinates. Stored bitmap/assembly/palette references ignored by the PC runtime, unknown flags/enemy bytes and trailing data are preserved.", "integrated", "sprites"),
    ("Game/chara/cell/c*.cel", "Sprite assemblies", "Edit existing current-PC sprite-cell chip index, signed X/Y and flip-X without changing frame/tile counts. The odd stored source bit, other flag bits, header word, prefix and trailing bytes are preserved.", "integrated", "spriteassemblies"),
    ("Game/chara/bmp + common Slot/Interval", "Sprite graphics and animations", "Current-PC sprite bitmaps and variable animation bodies are recognized but remain outside the bounded descriptor/assembly editors.", "not-integrated", None),
    ("Game/common/*DataTable*.dat", "Gameplay tables", "Candidate item/accessory/enemy/tech/shop tables exist in the Steam archive, but no independently verified typed record schema is claimed yet.", "not-integrated", None),
]


def build_data_map(store: OverlayStore) -> dict:
    available = set(store.archive.paths())
    rows = []
    for filename, controls, notes, status, target in ROWS:
        present = True
        if filename == "Localize/<lang>/msg/*.txt":
            present = any(path.startswith("Localize/") and "/msg/" in path and path.endswith(".txt") for path in available)
        elif filename.startswith("Game/common/MapJump"):
            present = {"Game/common/MapJumpOffsetTbl.dat", "Game/common/MapJumpDataTbl.dat"} <= available
        elif filename.startswith("Game/common/Takara"):
            present = {"Game/common/TakaraOffsetTbl.dat", "Game/common/TakaraDataTbl.dat"} <= available
        elif filename.startswith("Game/field/Mapinfo"):
            present = any(path.startswith("Game/field/Mapinfo/") for path in available)
        elif filename.startswith("Game/field/atel"):
            present = any(path.startswith("Game/field/atel/") for path in available)
        elif filename.startswith("Game/field/BGSetTable"):
            present = any(path.startswith("Game/field/BGSetTable/") for path in available)
        elif filename.startswith("Game/field/ChipTable"):
            present = any(path.startswith("Game/field/ChipTable/") for path in available)
        elif filename.startswith("Game/field/MapTable/"):
            present = any(path.startswith("Game/field/MapTable/") for path in available)
        elif filename.startswith("Game/field/PrioMap"):
            present = any(path.startswith(("Game/field/PrioMap/", "Game/field/MapTable/", "Game/field/map_bin/", "Game/field/weather_bin/")) for path in available)
        elif filename.startswith("Game/field/BGAnime"):
            present = any(path.startswith("Game/field/BGAnime/") for path in available)
        elif filename.startswith("Game/field/palette_bin"):
            present = any(path.startswith(("Game/field/palette_bin/", "Game/world/plt_bin/")) for path in available)
        elif filename.startswith("Game/common/bankc6"):
            present = "Game/common/bankc6.bin" in available
        elif filename.startswith("Game/world/Map/"):
            present = any(path.startswith("Game/world/Map/") for path in available)
        elif filename.startswith("Game/world/Id/"):
            present = any(path.startswith("Game/world/Id/") for path in available)
        elif filename.startswith("Game/world/SeId/"):
            present = any(path.startswith("Game/world/SeId/") for path in available)
        elif filename.startswith("Game/world/colanim_bin"):
            present = any(path.startswith("Game/world/colanim_bin/") for path in available)
        elif filename.startswith("Game/world/EventTable"):
            present = any(path.startswith("Game/world/EventTable/") for path in available)
        elif filename.startswith("Game/world/esl"):
            present = any(path.startswith("Game/world/") for path in available)
        elif filename.startswith("Game/chara/dat"):
            present = any(path.startswith("Game/chara/dat/") for path in available)
        elif filename.startswith("Game/chara/cell"):
            present = any(path.startswith("Game/chara/cell/") for path in available)
        elif filename.startswith("Game/chara/bmp"):
            present = any(path.startswith(("Game/chara/bmp/", "Game/common/Slot", "Game/common/Interval")) for path in available)
        elif filename.startswith("Game/common/*DataTable"):
            present = any(path.startswith("Game/common/") and "DataTable" in path for path in available)
        actual = status if present else "not-integrated"
        rows.append({
            "filename": filename,
            "controls": controls,
            "notes": notes if present else f"This family was not present in the selected Steam archive. {notes}",
            "coverage": "structured" if actual == "integrated" else ("source" if filename == "resources.bin" else "unavailable"),
            "status": actual,
            "openable": actual == "integrated" and target is not None,
            "target": target,
        })
    return {"rows": rows}
