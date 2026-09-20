"""Truthful Steam data-map coverage for the fresh Chrono Trigger plugin."""
from __future__ import annotations

from .project import OverlayStore


ROWS = [
    ("resources.bin", "Steam resource archive", "Read-only source container. Lexeditor reads ARC1 entries but never rewrites the installed archive.", "partial", "info"),
    ("Localize/<lang>/msg/*.txt", "Dialogue, menu and item text", "Edit keyed UTF-8 text records and save only the selected resource into the mod project.", "integrated", "text"),
    ("Game/common/MapJumpOffsetTbl.dat + MapJumpDataTbl.dat", "Area exits", "Edit existing Steam 8-byte exit records: trigger tile/size, destination, facing and destination position. Counts remain unchanged.", "integrated", "exits"),
    ("Game/common/TakaraOffsetTbl.dat + TakaraDataTbl.dat", "Treasure chests", "Edit existing Steam 6-byte treasure records for position and known item/gold contents. Alias sentinels and unknown trailing words are preserved.", "integrated", "treasure"),
    ("Game/field/Mapinfo/mapinfo_*.dat", "Area settings", "CTViewer documents the current PC header layout, but the fresh replacement has not yet added this editor.", "not-integrated", None),
    ("Game/field/atel/Atel_*.dat", "Events and cutscenes", "Public tools document substantial script structure, but variable command boundaries and safe resizing make this a later editor rather than part of the low-cost first slice.", "not-integrated", None),
    ("Game/field/MapTable + BGSetTable + ChipTable + map_bin", "Area maps", "CTViewer can render current-PC maps. The fresh replacement does not yet expose map painting or raster preview.", "not-integrated", None),
    ("Game/field/BGAnime/bganimeinfo_*.dat", "Animated map tiles", "Descriptor knowledge exists, but runtime phase and safe animation editing are not established for this replacement.", "not-integrated", None),
    ("Game/field/palette_bin/plt*.bin", "Area palettes", "CTViewer establishes 256-color PC palettes. A semantic color editor is feasible follow-up work but is not in the first checkpoint.", "not-integrated", None),
    ("Game/common/bankc6.bin + Game/world/*", "World maps and navigation", "CTViewer documents current-PC world headers, exits/triggers and scripts. The fresh replacement has not yet integrated them.", "not-integrated", None),
    ("Game/chara/*", "Characters and sprites", "Recognized current-PC assets; no format-specific editor is implemented yet.", "not-integrated", None),
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
        elif filename.startswith("Game/field/MapTable"):
            present = any(path.startswith("Game/field/MapTable/") for path in available)
        elif filename.startswith("Game/field/BGAnime"):
            present = any(path.startswith("Game/field/BGAnime/") for path in available)
        elif filename.startswith("Game/field/palette_bin"):
            present = any(path.startswith("Game/field/palette_bin/") for path in available)
        elif filename.startswith("Game/common/bankc6"):
            present = "Game/common/bankc6.bin" in available
        elif filename.startswith("Game/chara"):
            present = any(path.startswith("Game/chara/") for path in available)
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
