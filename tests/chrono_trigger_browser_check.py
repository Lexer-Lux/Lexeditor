"""Fixture-only rendered acceptance for the fresh Chrono Trigger Steam editor."""
from __future__ import annotations

# Dev caches and outputs live in the temp folder, never in the checkout.
DEV_CACHE = __import__("pathlib").Path(__import__("tempfile").gettempdir()) / "lexeditor-dev"
import json
from pathlib import Path
import shutil
import sys

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = Path(sys.argv[1]) if len(sys.argv) > 1 else DEV_CACHE / "chrono-trigger-browser"
ARTIFACTS.mkdir(parents=True, exist_ok=True)

DASHBOARD = {
    "game": {"root": r"C:\\Games\\Chrono Trigger", "archive": r"C:\\Games\\Chrono Trigger\\resources.bin", "resourceCount": 7421},
    "project": {"root": r"C:\\Mods\\ChronoFresh", "changeCount": 0},
    "languages": ["en"], "defaultLanguage": "en",
}
TEXT_PATH = "Localize/en/msg/cmes0.txt"
TEXT_FILES = {"language": "en", "rows": [TEXT_PATH, "Localize/en/msg/item.txt"]}
MESSAGES = {
    "path": TEXT_PATH, "source": "vanilla", "sha256": "text-sha-1",
    "rows": [
        {"token": "0:FLD_001", "key": "FLD_001", "text": "Welcome to the fair.", "line": 0},
        {"token": "1:FLD_002", "key": "FLD_002", "text": "The gate is open.", "line": 1},
        {"token": "2:FLD_003", "key": "FLD_003", "text": "Need anything?", "line": 2},
    ],
}
SCENES = {
    "language": "en", "source": "mine",
    "rows": [
        {"token": "1", "id": 1, "name": "Millennial Fair", "path": "Game/field/Mapinfo/mapinfo_1.dat",
         "source": "vanilla", "sha256": "scene-sha-1", "musicIndex": 10,
         "layer12TilesetIndex": 1, "layer12AssemblyIndex": 2, "layer3TilesetIndex": 3,
         "paletteIndex": 4, "paletteAnimationIndex": 5, "mapIndex": 6, "chipAnimationIndex": 7,
         "scriptIndex": 8, "unknownWord": 48879, "cameraUnbounded": False,
         "scrollLeft": 0, "scrollTop": 1, "scrollRight": 14, "scrollBottom": 15, "trailingBytes": 2},
        {"token": "2", "id": 2, "name": "Guardia Forest", "path": "Game/field/Mapinfo/mapinfo_2.dat",
         "source": "vanilla", "sha256": "scene-sha-2", "musicIndex": 12,
         "layer12TilesetIndex": 4, "layer12AssemblyIndex": 5, "layer3TilesetIndex": 6,
         "paletteIndex": 7, "paletteAnimationIndex": 8, "mapIndex": 9, "chipAnimationIndex": 10,
         "scriptIndex": 11, "unknownWord": 4660, "cameraUnbounded": True,
         "scrollLeft": 128, "scrollTop": 0, "scrollRight": 0, "scrollBottom": 0, "trailingBytes": 0},
    ],
}
SCENE_MAP_FILES = {"rows": [{"path": "Game/field/MapTable/MapTable_0006.dat", "id": 6, "label": "Area map 6",
                              "layer1": "16×16", "layer2": "16×16", "layer3": "disabled"}]}
SCENE_MAP = {
    "path": "Game/field/MapTable/MapTable_0006.dat", "mapId": 6, "source": "vanilla",
    "sha256": "scene-map-sha-1", "layer1Width": 16, "layer1Height": 16,
    "layer2Width": 16, "layer2Height": 16, "layer3Width": 16, "layer3Height": 16,
    "layer3Enabled": False, "scrollBits": 0, "scrollL2": 0x21, "scrollL3": 0x43,
    "screenFlags": 0x5A, "effectFlags": 0xCB, "propertyBytes": 7, "propertyOffset": 518,
    "rows": [
        {"token": "6:1:0", "mapId": 6, "layer": 1, "index": 0, "xTile": 0, "yTile": 0,
         "storedTile": 3, "upperBank": True, "tileIndex": 259},
        {"token": "6:2:0", "mapId": 6, "layer": 2, "index": 0, "xTile": 0, "yTile": 0,
         "storedTile": 4, "upperBank": False, "tileIndex": 4},
    ],
}
SCENE_RENDER = {
    "token": "6", "mapId": 6, "path": "Game/field/MapTable/MapTable_0006.dat",
    "source": "vanilla", "sha256": "scene-render-sha-1",
    "scrollL2XCode": 1, "scrollL2YCode": 2, "scrollL2XSpeed": 3.75, "scrollL2YSpeed": 7.5,
    "scrollL3XCode": 3, "scrollL3YCode": 4, "scrollL3XSpeed": 15.0, "scrollL3YSpeed": 30.0,
    "unknownEffectBit3": True, "preservedBitsByte": 0, "layer3Enabled": False, "scrollModeBits": 0,
    "layer1Main": False, "layer2Main": True, "layer3Main": False, "spritesMain": True,
    "layer1Sub": True, "layer2Sub": False, "layer3Sub": True, "spritesSub": False,
    "effectLayer1": True, "effectLayer2": True, "effectLayer3": False, "effectSprites": False,
    "effectDefaultColor": False, "effectHalfIntensity": True, "effectSubtract": True,
}
SCENE_PROPS = {
    "path": "Game/field/MapTable/MapTable_0006.dat", "mapId": 6, "source": "vanilla",
    "sha256": "scene-props-sha-1", "width": 16, "height": 16, "expectedTiles": 256,
    "expandedTiles": 256, "propertyOffset": 518, "propertyBytes": 7, "trailingPropertyBytes": 0,
    "rows": [
        {"token": "6:prop:0", "mapId": 6, "runId": 0, "byteOffset": 518, "compressed": False,
         "repeatCount": 1, "startTile": 0, "endTile": 0, "coveredTiles": 1,
         "layer1UpperBank": True, "layer2UpperBank": False, "collisionCode": 0, "collisionName": "None",
         "moveDirection": 0, "moveDirectionName": "North", "moveSpeed": 0, "doorTrigger": False,
         "unknownSecondBit5": False, "priorityTop": False, "npcCollisionBattle": False,
         "zPlane": 0, "collisionIgnoreZ": False, "collisionInverted": False, "unknownThirdBit4": False,
         "zNeutral": False, "priorityBottom": False, "npcCollision": False},
        {"token": "6:prop:1", "mapId": 6, "runId": 1, "byteOffset": 521, "compressed": True,
         "repeatCount": 255, "startTile": 1, "endTile": 255, "coveredTiles": 255,
         "layer1UpperBank": False, "layer2UpperBank": False, "collisionCode": 0, "collisionName": "None",
         "moveDirection": 0, "moveDirectionName": "North", "moveSpeed": 0, "doorTrigger": False,
         "unknownSecondBit5": True, "priorityTop": False, "npcCollisionBattle": False,
         "zPlane": 0, "collisionIgnoreZ": False, "collisionInverted": False, "unknownThirdBit4": True,
         "zNeutral": False, "priorityBottom": False, "npcCollision": False},
    ],
}
EXITS = {
    "source": "vanilla", "dataSha256": "exit-data-1", "offsetSha256": "exit-offset-1",
    "rows": [
        {"token": "12:0", "sceneId": 12, "exitId": 0, "xTile": 4, "yTile": 7, "lengthTiles": 2,
         "orientation": "horizontal", "destinationId": 18, "destinationKind": "scene", "facing": 1,
         "halfTileLeft": False, "halfTileUp": True, "targetX": 9, "targetY": 11,
         "unknownFacingBits": 160, "byteOffset": 4},
        {"token": "12:1", "sceneId": 12, "exitId": 1, "xTile": 14, "yTile": 2, "lengthTiles": 1,
         "orientation": "vertical", "destinationId": 496, "destinationKind": "world", "facing": 2,
         "halfTileLeft": True, "halfTileUp": False, "targetX": 18, "targetY": 20,
         "unknownFacingBits": 64, "byteOffset": 12},
    ],
}
TREASURE = {
    "source": "vanilla", "dataSha256": "treasure-data-1", "offsetSha256": "treasure-offset-1",
    "kinds": ["weapon", "armor", "helmet", "accessory", "consumable", "item", "gold"],
    "rows": [
        {"token": "12:0", "sceneId": 12, "treasureId": 0, "xTile": 5, "yTile": 8, "alias": False,
         "aliasScene": None, "kind": "armor", "gold": None, "localIndex": 2, "globalItemId": 113,
         "itemName": "Ruby Vest", "trailingWord": 51966, "editable": True, "byteOffset": 4},
        {"token": "13:0", "sceneId": 13, "treasureId": 0, "xTile": 0, "yTile": 0, "alias": True,
         "aliasScene": 12, "kind": "weapon", "gold": None, "localIndex": 12, "globalItemId": 12,
         "itemName": "", "trailingWord": 48879, "editable": False, "byteOffset": 10},
    ],
}
PALETTE_FILES = {"rows": [{"path": "Game/field/palette_bin/plt4.bin", "id": 4, "kind": "Area", "label": "Area palette 4"}]}
PALETTE = {
    "path": "Game/field/palette_bin/plt4.bin", "source": "vanilla", "sha256": "palette-sha-1",
    "prefixHex": "1234", "trailingBytes": 1,
    "rows": [
        {"token": str(index), "index": index, "hex": "#FF0000" if index == 0 else "#000000",
         "red5": 31 if index == 0 else 0, "green5": 0, "blue5": 0,
         "preservedBit15": index == 0}
        for index in range(256)
    ],
}
WORLD_ROW = {
    "token": "0", "id": 0, "name": "World 0", "source": "vanilla", "byteOffset": 0xFD10,
    "paletteIndex": 10, "paletteAnimationIndex": 11,
    "layer12AssemblyIndex": 16, "mapIndex": 17, "mapPropertiesIndex": 18,
    "musicPropertiesIndex": 19, "layer3AssemblyIndex": 20, "exitsIndex": 21, "scriptIndex": 22,
}
WORLD_ROW.update({f"layer12Graphics{index}": index for index in range(8)})
WORLD_ROW.update({f"layer3Graphics{index}": 8 + index for index in range(2)})
WORLD_ROW.update({f"spriteGraphics{index}": 12 + index for index in range(4)})
WORLDS = {"path": "Game/common/bankc6.bin", "source": "vanilla", "sha256": "world-sha-1", "rows": [WORLD_ROW]}
WORLD_FILES = {
    "tiles": [{"path": "Game/world/Map/Map_0000.dat", "id": 0, "label": "World map 0"}],
    "properties": [{"path": "Game/world/Id/Id_0000.dat", "id": 0, "label": "World properties 0"}],
    "music": [{"path": "Game/world/SeId/SeId_0000.dat", "id": 0, "label": "World music 0"}],
    "colors": [{"path": "Game/world/colanim_bin/0_colanim.bin", "id": 0, "label": "World colors 0"}],
}
WORLD_MAP = {
    "path": "Game/world/Map/Map_0000.dat", "mapId": 0, "source": "vanilla",
    "sha256": "world-map-sha-1", "width": 96, "height": 64, "trailingBytes": 1,
    "rows": [
        {"token": "0:1:0", "mapId": 0, "layer": 1, "index": 0, "xTile": 0, "yTile": 0, "tileIndex": 3},
        {"token": "0:2:0", "mapId": 0, "layer": 2, "index": 0, "xTile": 0, "yTile": 0, "tileIndex": 260},
    ],
}
WORLD_PROPS = {
    "path": "Game/world/Id/Id_0000.dat", "fileId": 0, "source": "vanilla",
    "sha256": "world-props-sha-1", "trailingBytes": 1,
    "rows": [{"token": "0:0", "fileId": 0, "tileIndex": 256,
              "topLeft": 1, "topRight": 2, "bottomLeft": 3, "bottomRight": 4}],
}
WORLD_MUSIC = {
    "path": "Game/world/SeId/SeId_0000.dat", "fileId": 0, "source": "vanilla",
    "sha256": "world-music-sha-1", "trailingBytes": 1,
    "rows": [{"token": "0:0", "fileId": 0, "index": 0, "xTile": 0, "yTile": 0,
              "leftMusic": 10, "rightMusic": 5}],
}
WORLD_COLORS = {
    "path": "Game/world/colanim_bin/0_colanim.bin", "fileId": 0, "source": "vanilla",
    "sha256": "world-colors-sha-1", "trailingBytes": 1,
    "rows": [
        {"token": "0", "index": 0, "hex": "#FF0000", "red5": 31, "green5": 0, "blue5": 0, "preservedBit15": True},
        {"token": "1", "index": 1, "hex": "#00FF00", "red5": 0, "green5": 31, "blue5": 0, "preservedBit15": False},
    ],
}
GRAPHICS_SETS = {
    "source": "vanilla",
    "rows": [{"token": "4", "id": 4, "path": "Game/field/BGSetTable/bgsettable_4.dat",
              "source": "vanilla", "sha256": "graphics-sha-1", "trailingBytes": 1,
              **{f"graphicsSet{i}": value for i, value in enumerate([1,2,3,4,5,6,7,255])}}],
}
ASSEMBLIES = {
    "source": "vanilla",
    "files": [{"path": "Game/field/ChipTable/ChipTable_0004.dat", "kind": "layer12",
               "fileId": 4, "tileCount": 512, "source": "vanilla", "sha256": "assembly-sha-1",
               "trailingBytes": 1}],
    "rows": [
        {"token": "layer12:4:0:0", "kind": "layer12", "fileId": 4, "tileId": 0,
         "corner": 0, "cornerName": "Top left", "path": "Game/field/ChipTable/ChipTable_0004.dat",
         "source": "vanilla", "sha256": "assembly-sha-1", "byteOffset": 0,
         "chipIndex": 300, "flipHorizontal": True, "flipVertical": False,
         "paletteIndex": 5, "priority": True, "unknownPriorityBits": 160,
         "fileTrailingBytes": 1},
        {"token": "layer12:4:0:1", "kind": "layer12", "fileId": 4, "tileId": 0,
         "corner": 1, "cornerName": "Top right", "path": "Game/field/ChipTable/ChipTable_0004.dat",
         "source": "vanilla", "sha256": "assembly-sha-1", "byteOffset": 3,
         "chipIndex": 0, "flipHorizontal": False, "flipVertical": False,
         "paletteIndex": 0, "priority": False, "unknownPriorityBits": 0,
         "fileTrailingBytes": 1},
    ],
}
SPRITES = {
    "source": "vanilla",
    "rows": [{
        "token": "5", "id": 5, "path": "Game/chara/dat/c005.dat",
        "source": "vanilla", "sha256": "sprite-sha-1",
        "storedBitmapIndex": 9, "storedAssemblyIndex": 8, "storedPaletteIndex": 7,
        "sizeGroupCode": 0, "primaryEnemy": True, "unknownSizeFlags": 0xA4,
        "animationIndex": 5, "unknownFlags": 0xD2, "enemyDescriptor": True,
        "handX": -2, "handY": 3, "enemyUnknown1": 0x11, "enemyUnknown2": 0x22,
        "enemyUnknown3": 0x33, "trailingBytes": 1,
    }],
}
SPRITE_ASSEMBLIES = {
    "source": "vanilla",
    "files": [{"path": "Game/chara/cell/c005.cel", "fileId": 5, "source": "vanilla",
               "sha256": "sprite-assembly-sha-1", "frameCount": 2, "headerWord": 0xBEEF,
               "prefixHex": "AABBCC", "trailingBytes": 1}],
    "rows": [
        {"token": "5:0:0", "fileId": 5, "frameId": 0, "tileId": 0,
         "path": "Game/chara/cell/c005.cel", "source": "vanilla", "sha256": "sprite-assembly-sha-1",
         "byteOffset": 8, "frameTileCount": 2, "chipIndex": 300, "weirdSourceBit": True,
         "x": -5, "y": -25, "isTop": True, "flipHorizontal": True, "unknownFlags": 0xA0,
         "fileTrailingBytes": 1, "frameCount": 2, "headerWord": 0xBEEF, "prefixHex": "AABBCC"},
        {"token": "5:0:1", "fileId": 5, "frameId": 0, "tileId": 1,
         "path": "Game/chara/cell/c005.cel", "source": "vanilla", "sha256": "sprite-assembly-sha-1",
         "byteOffset": 13, "frameTileCount": 2, "chipIndex": 0, "weirdSourceBit": False,
         "x": 1, "y": 2, "isTop": False, "flipHorizontal": False, "unknownFlags": 0x02,
         "fileTrailingBytes": 1, "frameCount": 2, "headerWord": 0xBEEF, "prefixHex": "AABBCC"},
    ],
}
CHIP_ANIMATIONS = {
    "source": "vanilla",
    "files": [{"path": "Game/field/BGAnime/bganimeinfo_4.dat", "fileId": 4, "source": "vanilla",
               "sha256": "anim-sha-1", "declaredCount": 2, "parsedCount": 2,
               "stoppedByTerminator": False, "terminatorOffset": None, "trailingBytes": 1}],
    "rows": [
        {"token": "4:0", "fileId": 4, "animationId": 0, "path": "Game/field/BGAnime/bganimeinfo_4.dat",
         "sha256": "anim-sha-1", "source": "vanilla", "byteOffset": 1, "frameCount": 2,
         "destinationChip": 2, "destinationOffsetRemainder": 0, "editable": True,
         "durationCode0": 0x10, "durationTicks0": 16, "durationLowBits0": 0x0A,
         "sourceChip0": 3, "sourceOffsetRemainder0": 0,
         "durationCode1": 0x40, "durationTicks1": 8, "durationLowBits1": 0x0B,
         "sourceChip1": 4, "sourceOffsetRemainder1": 0,
         "fileTrailingBytes": 1, "declaredAnimationCount": 2},
        {"token": "4:1", "fileId": 4, "animationId": 1, "path": "Game/field/BGAnime/bganimeinfo_4.dat",
         "sha256": "anim-sha-1", "source": "vanilla", "byteOffset": 10, "frameCount": 1,
         "destinationChip": 5, "destinationOffsetRemainder": 0, "editable": True,
         "durationCode0": 0x80, "durationTicks0": 4, "durationLowBits0": 0,
         "sourceChip0": 6, "sourceOffsetRemainder0": 0,
         "fileTrailingBytes": 1, "declaredAnimationCount": 2},
    ],
}
WORLD_NAVIGATION = {
    "language": "en", "source": "vanilla",
    "files": [{"path": "Game/world/EventTable/EventTable_0004.dat", "tableId": 4, "source": "vanilla",
               "sha256": "world-nav-sha-1", "exitCount": 2, "triggerCount": 1, "storedTriggerCount": 2,
               "unknownCount": 1, "scriptAddressCount": 2, "trailingBytes": 2}],
    "rows": [
        {"token": "4:exit:0", "recordType": "exit", "tableId": 4, "recordId": 0,
         "path": "Game/world/EventTable/EventTable_0004.dat", "sha256": "world-nav-sha-1", "source": "vanilla",
         "byteOffset": 1, "xTile": 5, "enabled": True, "yTile": 7, "unknownYBits": 192,
         "nameIndex": 0, "name": "Truce Canyon", "scripted": False, "destinationScene": 12,
         "scriptAddressIndex": None, "facing": 2, "halfTileLeft": True, "halfTileUp": False,
         "unknownFacingBits": 161, "targetX": 9, "targetY": 10, "scriptAddressCount": 2},
        {"token": "4:exit:1", "recordType": "exit", "tableId": 4, "recordId": 1,
         "path": "Game/world/EventTable/EventTable_0004.dat", "sha256": "world-nav-sha-1", "source": "vanilla",
         "byteOffset": 9, "xTile": 2, "enabled": True, "yTile": 3, "unknownYBits": 0,
         "nameIndex": 1, "name": "Medina", "scripted": True, "destinationScene": None,
         "scriptAddressIndex": 1, "facing": None, "halfTileLeft": False, "halfTileUp": True,
         "unknownFacingBits": 64, "targetX": 0, "targetY": 0, "scriptAddressCount": 2},
        {"token": "4:trigger:0", "recordType": "trigger", "tableId": 4, "recordId": 0,
         "path": "Game/world/EventTable/EventTable_0004.dat", "sha256": "world-nav-sha-1", "source": "vanilla",
         "byteOffset": 18, "xTile": 4, "enabled": True, "yTile": 5, "scriptAddressIndex": 0,
         "scriptAddressCount": 2},
    ],
}
DATA_MAP = {"rows": [
    {"filename": "resources.bin", "controls": "Steam resource archive", "notes": "Read-only ARC1 source.", "coverage": "source", "status": "partial", "openable": False, "target": "info"},
    {"filename": "Localize/<lang>/msg/*.txt", "controls": "Dialogue, menu and item text", "notes": "Keyed text editor.", "coverage": "structured", "status": "integrated", "openable": True, "target": "text"},
    {"filename": "Game/common/MapJumpOffsetTbl.dat + MapJumpDataTbl.dat", "controls": "Area exits", "notes": "Existing fixed-size exits.", "coverage": "structured", "status": "integrated", "openable": True, "target": "exits"},
    {"filename": "Game/common/TakaraOffsetTbl.dat + TakaraDataTbl.dat", "controls": "Treasure chests", "notes": "Existing fixed-size treasure.", "coverage": "structured", "status": "integrated", "openable": True, "target": "treasure"},
    {"filename": "Game/field/Mapinfo/mapinfo_*.dat", "controls": "Area settings", "notes": "Fixed Steam area headers.", "coverage": "structured", "status": "integrated", "openable": True, "target": "scenes"},
    {"filename": "Game/field/MapTable/MapTable_*.dat", "controls": "Area map tiles", "notes": "Fixed layer tile bytes; RLE properties preserved.", "coverage": "structured", "status": "integrated", "openable": True, "target": "scenemaps"},
    {"filename": "Game/field/MapTable/MapTable_*.dat header", "controls": "Area render settings", "notes": "Fixed scroll, screen and effect masks.", "coverage": "structured", "status": "integrated", "openable": True, "target": "scenerender"},
    {"filename": "Game/field/MapTable/MapTable_*.dat RLE properties", "controls": "Area collision and movement", "notes": "Existing RLE property runs; repeat counts and unknown bits preserved.", "coverage": "structured", "status": "integrated", "openable": True, "target": "sceneprops"},
    {"filename": "Game/field/palette_bin/plt*.bin + Game/world/plt_bin/plt*.bin", "controls": "Area and world palettes", "notes": "Fixed 256-color RGB555 palettes.", "coverage": "structured", "status": "integrated", "openable": True, "target": "palettes"},
    {"filename": "Game/field/BGSetTable/bgsettable_*.dat", "controls": "Tileset graphics sets", "notes": "Eight fixed graphics-set references.", "coverage": "structured", "status": "integrated", "openable": True, "target": "tilesets"},
    {"filename": "Game/field/ChipTable/ChipTable_*.dat + ChipTableBg3_*.dat", "controls": "Tile assemblies", "notes": "Fixed 3-byte tile corners.", "coverage": "structured", "status": "integrated", "openable": True, "target": "assemblies"},
    {"filename": "Game/field/BGAnime/bganimeinfo_*.dat", "controls": "Animated map tiles", "notes": "Existing fixed-count current-PC chip animations.", "coverage": "structured", "status": "integrated", "openable": True, "target": "animations"},
    {"filename": "Game/chara/dat/c*.dat", "controls": "Sprite descriptors", "notes": "Bounded current-PC sprite header fields.", "coverage": "structured", "status": "integrated", "openable": True, "target": "sprites"},
    {"filename": "Game/chara/cell/c*.cel", "controls": "Sprite assemblies", "notes": "Existing fixed frame/tile records.", "coverage": "structured", "status": "integrated", "openable": True, "target": "spriteassemblies"},
    {"filename": "Game/common/bankc6.bin @ 0xFD10", "controls": "World settings", "notes": "Seven fixed 23-byte Steam world headers.", "coverage": "structured", "status": "integrated", "openable": True, "target": "worlds"},
    {"filename": "Game/world/Map/Map_*.dat", "controls": "World map tiles", "notes": "Two fixed 96x64 layers.", "coverage": "structured", "status": "integrated", "openable": True, "target": "worldmaps"},
    {"filename": "Game/world/Id/Id_*.dat", "controls": "World tile properties", "notes": "Fixed property nibbles.", "coverage": "structured", "status": "integrated", "openable": True, "target": "worldprops"},
    {"filename": "Game/world/SeId/SeId_*.dat", "controls": "World music transitions", "notes": "Fixed music nibbles.", "coverage": "structured", "status": "integrated", "openable": True, "target": "worldmusic"},
    {"filename": "Game/world/colanim_bin/*_colanim.bin", "controls": "World palette-animation colors", "notes": "Flat RGB555 colors.", "coverage": "structured", "status": "integrated", "openable": True, "target": "worldcolors"},
    {"filename": "Game/world/EventTable/EventTable_*.dat", "controls": "World exits and triggers", "notes": "Existing fixed current-PC world navigation records.", "coverage": "structured", "status": "integrated", "openable": True, "target": "worldnav"},
    {"filename": "Game/world/esl/Event_*.dat + map_bin + Chip + gif", "controls": "World scripts and graphics", "notes": "Remaining variable scripts/raw graphics.", "coverage": "unavailable", "status": "not-integrated", "openable": False, "target": None},
]}
CHANGES = {"rows": []}


def editor_html() -> str:
    html = (ROOT / "plugins/chrono_trigger/editor.html").read_text(encoding="utf-8")
    html = html.replace("<head>", '<head><base href="http://127.0.0.1:9/">', 1)
    html = html.replace(
        '<link rel="stylesheet" href="/shared/framework.css">',
        "<style>" + (ROOT / "ui/framework.css").read_text(encoding="utf-8") + "</style>",
    )
    html = html.replace(
        '<link rel="stylesheet" href="/editor.css">',
        "<style>" + (ROOT / "plugins/chrono_trigger/editor.css").read_text(encoding="utf-8") + "</style>",
    )
    fixtures = {
        "dashboard": DASHBOARD, "textFiles": TEXT_FILES, "messages": MESSAGES, "scenes": SCENES,
        "sceneMapFiles": SCENE_MAP_FILES, "sceneMap": SCENE_MAP, "sceneProps": SCENE_PROPS, "sceneRender": SCENE_RENDER, "exits": EXITS, "treasure": TREASURE, "paletteFiles": PALETTE_FILES, "palette": PALETTE, "worlds": WORLDS, "worldFiles": WORLD_FILES, "worldMap": WORLD_MAP, "worldProps": WORLD_PROPS, "worldMusic": WORLD_MUSIC, "worldColors": WORLD_COLORS, "worldNavigation": WORLD_NAVIGATION, "animations": CHIP_ANIMATIONS, "graphicsSets": GRAPHICS_SETS, "assemblies": ASSEMBLIES, "sprites": SPRITES, "spriteAssemblies": SPRITE_ASSEMBLIES, "dataMap": DATA_MAP, "changes": CHANGES,
    }
    stub = r"""
    window.__posts=[];
    window.__fixtures=FIXTURES;
    window.fetch=async function(input,options={}){
      const u=new URL(String(input),"http://fixture/");
      const path=u.pathname, f=window.__fixtures;
      let result=null, status=200;
      if((options.method||"GET").toUpperCase()==="POST"){
        const body=JSON.parse(options.body||"{}");window.__posts.push({path,body});
        if(path==="/api/messages/save"){
          for(const edit of body.edits||[]){
            const row=f.messages.rows.find(value=>value.line===edit.line&&value.key===edit.key);
            if(row)row.text=edit.text;
          }
          f.messages.sha256="text-sha-2";f.messages.source="project";
          f.changes.rows=[{path:f.messages.path,size:123,status:"modified",sha256:"fixture"}];
          result=f.messages;
        }else if(path==="/api/export"){
          result={path:"C:/Mods/ChronoFresh/build/ChronoFresh.ctp",fileCount:f.changes.rows.length,files:f.changes.rows.map(x=>x.path)};
        }else if(path==="/api/scenes/save"){
          const row=f.scenes.rows.find(value=>value.id===body.id);
          if(row){Object.assign(row,body.values||{});row.sha256="scene-sha-saved";row.source="project";}
          result=row;
        }else if(path==="/api/scene-map/save"){
          for(const edit of body.edits||[]){const row=f.sceneMap.rows.find(value=>value.token===edit.token);if(row){Object.assign(row,edit.values||{});row.storedTile=row.tileIndex-(row.upperBank?256:0);}}
          f.sceneMap.sha256="scene-map-sha-2";f.sceneMap.source="project";result=f.sceneMap;
        }else if(path==="/api/scene-render-settings/save"){
          Object.assign(f.sceneRender,body.values||{});f.sceneRender.sha256="scene-render-sha-2";f.sceneRender.source="project";result=f.sceneRender;
        }else if(path==="/api/scene-properties/save"){
          for(const edit of body.edits||[]){
            const row=f.sceneProps.rows.find(value=>value.token===edit.token);
            if(row){Object.assign(row,edit.values||{});if("collisionCode" in (edit.values||{}))row.collisionName={30:"Ladder"}[row.collisionCode]||row.collisionName;if("moveDirection" in (edit.values||{}))row.moveDirectionName=["North","South","East","West"][row.moveDirection];}
          }
          f.sceneProps.sha256="scene-props-sha-2";f.sceneProps.source="project";result=f.sceneProps;
        }else if(path==="/api/palette/save"){
          for(const edit of body.edits||[]){const row=f.palette.rows.find(value=>value.token===edit.token);if(row)row.hex=edit.hex;}
          f.palette.sha256="palette-sha-saved";f.palette.source="project";result=f.palette;
        }else if(path==="/api/worlds/save"){
          for(const edit of body.edits||[]){
            const row=f.worlds.rows.find(value=>value.token===edit.token);
            if(row)Object.assign(row,edit.values||{});
          }
          f.worlds.sha256="world-sha-saved";f.worlds.source="project";result=f.worlds;
        }else if(path==="/api/world-map/save"){
          for(const edit of body.edits||[]){const row=f.worldMap.rows.find(value=>value.token===edit.token);if(row)Object.assign(row,edit.values||{});}
          f.worldMap.sha256="world-map-sha-2";f.worldMap.source="project";result=f.worldMap;
        }else if(path==="/api/world-properties/save"){
          for(const edit of body.edits||[]){const row=f.worldProps.rows.find(value=>value.token===edit.token);if(row)Object.assign(row,edit.values||{});}
          f.worldProps.sha256="world-props-sha-2";f.worldProps.source="project";result=f.worldProps;
        }else if(path==="/api/world-music/save"){
          for(const edit of body.edits||[]){const row=f.worldMusic.rows.find(value=>value.token===edit.token);if(row)Object.assign(row,edit.values||{});}
          f.worldMusic.sha256="world-music-sha-2";f.worldMusic.source="project";result=f.worldMusic;
        }else if(path==="/api/world-colors/save"){
          for(const edit of body.edits||[]){const row=f.worldColors.rows.find(value=>value.token===edit.token);if(row)row.hex=edit.hex;}
          f.worldColors.sha256="world-colors-sha-2";f.worldColors.source="project";result=f.worldColors;
        }else if(path==="/api/world-navigation/save"){
          for(const edit of body.edits||[]){
            const row=f.worldNavigation.rows.find(value=>value.token===edit.token);
            if(row)Object.assign(row,edit.values||{});
          }
          for(const row of f.worldNavigation.rows){row.sha256="world-nav-sha-2";row.source="project";}
          result={path:body.path,tableId:4,source:"project",sha256:"world-nav-sha-2",
                  rows:f.worldNavigation.rows,exitCount:2,triggerCount:1,storedTriggerCount:2,
                  unknownCount:1,scriptAddressCount:2,trailingBytes:2};
        }else if(path==="/api/chip-animations/save"){
          for(const edit of body.edits||[]){
            const row=f.animations.rows.find(value=>value.token===edit.token);
            if(row){
              Object.assign(row,edit.values||{});
              if("durationCode0" in (edit.values||{}))row.durationTicks0={16:16,32:12,64:8,128:4}[row.durationCode0]||null;
            }
          }
          for(const row of f.animations.rows){row.sha256="anim-sha-2";row.source="project";}
          result={path:body.path,fileId:4,source:"project",sha256:"anim-sha-2",
                  declaredCount:2,parsedCount:2,stoppedByTerminator:false,terminatorOffset:null,
                  trailingBytes:1,rows:f.animations.rows};
        }else if(path==="/api/graphics-sets/save"){
          const row=f.graphicsSets.rows.find(value=>value.path===body.path);
          if(row){Object.assign(row,body.values||{});row.sha256="graphics-sha-2";row.source="project";}
          result=row;
        }else if(path==="/api/tile-assemblies/save"){
          for(const edit of body.edits||[]){
            const row=f.assemblies.rows.find(value=>value.token===edit.token);
            if(row)Object.assign(row,edit.values||{});
          }
          for(const row of f.assemblies.rows){row.sha256="assembly-sha-2";row.source="project";}
          result={path:body.path,kind:"layer12",fileId:4,tileCount:512,source:"project",
                  sha256:"assembly-sha-2",trailingBytes:1,rows:f.assemblies.rows};
        }else if(path==="/api/sprite-assemblies/save"){
          for(const edit of body.edits||[]){const row=f.spriteAssemblies.rows.find(value=>value.token===edit.token);if(row)Object.assign(row,edit.values||{});}
          for(const row of f.spriteAssemblies.rows){row.sha256="sprite-assembly-sha-2";row.source="project";}
          result={path:body.path,fileId:5,source:"project",sha256:"sprite-assembly-sha-2",
                  frameCount:2,headerWord:0xBEEF,prefixHex:"AABBCC",trailingBytes:1,
                  rows:f.spriteAssemblies.rows};
        }else if(path==="/api/sprite-headers/save"){
          const row=f.sprites.rows.find(value=>value.path===body.path);
          if(row){Object.assign(row,body.values||{});row.sha256="sprite-sha-2";row.source="project";}
          result=row;
        }else if(path==="/api/exits/save")result=f.exits;
        else if(path==="/api/treasure/save")result=f.treasure;
        else result={};
      }else if(path==="/api/dashboard")result=f.dashboard;
      else if(path==="/api/datamap")result=f.dataMap;
      else if(path==="/api/changes")result=f.changes;
      else if(path==="/api/text-files")result=f.textFiles;
      else if(path==="/api/messages")result=f.messages;
      else if(path==="/api/scenes")result=f.scenes;
      else if(path==="/api/scene-map-files")result=f.sceneMapFiles;
      else if(path==="/api/scene-map")result=f.sceneMap;
      else if(path==="/api/scene-properties")result=f.sceneProps;
      else if(path==="/api/scene-render-settings")result=f.sceneRender;
      else if(path==="/api/palette-files")result=f.paletteFiles;
      else if(path==="/api/palette")result=f.palette;
      else if(path==="/api/worlds")result=f.worlds;
      else if(path==="/api/world-files")result={rows:f.worldFiles[u.searchParams.get("kind")]||[]};
      else if(path==="/api/world-map")result=f.worldMap;
      else if(path==="/api/world-properties")result=f.worldProps;
      else if(path==="/api/world-music")result=f.worldMusic;
      else if(path==="/api/world-colors")result=f.worldColors;
      else if(path==="/api/world-navigation")result=f.worldNavigation;
      else if(path==="/api/chip-animations")result=f.animations;
      else if(path==="/api/graphics-sets")result=f.graphicsSets;
      else if(path==="/api/tile-assemblies")result=f.assemblies;
      else if(path==="/api/sprite-headers")result=f.sprites;
      else if(path==="/api/sprite-assemblies")result=f.spriteAssemblies;
      else if(path==="/api/exits")result=f.exits;
      else if(path==="/api/treasure")result=f.treasure;
      else {status=404;result={error:"Unknown fixture request "+path};}
      return new Response(JSON.stringify(result),{status,headers:{"Content-Type":"application/json"}});
    };
    """.replace("FIXTURES", json.dumps(fixtures))
    html = html.replace(
        '<script src="/shared/framework.js"></script>',
        "<script>" + stub + "</script><script>" + (ROOT / "ui/framework.js").read_text(encoding="utf-8") + "</script>",
    )
    html = html.replace(
        '<script src="/editor.js"></script>',
        "<script>" + (ROOT / "plugins/chrono_trigger/editor.js").read_text(encoding="utf-8") + "</script>",
    )
    return html


def metrics(page):
    return page.evaluate("""() => {
      const main=document.querySelector('#main')?.getBoundingClientRect();
      return {bodyHeight:document.body.scrollHeight, viewportHeight:innerHeight,
              bodyWidth:document.body.scrollWidth, viewportWidth:innerWidth,
              mainBottom:main?.bottom||0};
    }""")


def main():
    errors=[]; results=[]
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(
            executable_path=shutil.which("chromium") or None, headless=True,
            args=["--no-sandbox","--use-gl=angle","--use-angle=swiftshader","--enable-unsafe-swiftshader"],
        )
        try:
            cases = [
                (1200, 800, 1.0, "1200"),
                (900, 620, 1.0, "900"),
                # WebView2 UI scale is page zoom. A 900x620 physical window at
                # 150% exposes roughly a 600x413 CSS viewport; device scale keeps
                # screenshots at the corresponding physical density.
                (600, 413, 1.5, "900-150pct"),
            ]
            for width,height,scale,shot in cases:
                page=browser.new_page(viewport={"width":width,"height":height},
                                      device_scale_factor=scale)
                page.on("pageerror",lambda error: errors.append(str(error)))
                page.route("http://127.0.0.1:9/**",lambda route: route.fulfill(status=200,body="<html></html>",content_type="text/html"))
                page.goto("http://127.0.0.1:9/")
                page.set_content(editor_html(),wait_until="domcontentloaded")
                page.wait_for_selector(".lex-detail-panel-body textarea")
                assert not errors,errors
                assert page.locator(".lex-paged-list-detail").count()==1
                page.locator(".lex-detail-panel-body textarea").fill("Changed in rendered acceptance")
                page.wait_for_function("!document.querySelector('#global-save')?.disabled")
                page.locator("#global-save").click()
                page.wait_for_function("document.querySelector('#global-save')?.disabled && document.querySelector('.lex-detail-panel-body textarea')?.value.includes('rendered acceptance')")
                assert page.evaluate("window.__posts.some(value=>value.path==='/api/messages/save')")
                page.screenshot(path=str(ARTIFACTS/f"text-{shot}.png"),full_page=True)

                page.locator(".lex-tab-label-text",has_text="Areas").click()
                page.locator("#main").get_by_text("PC WORD", exact=True).wait_for()
                assert "Millennial Fair" in page.locator("#main").inner_text()
                assert "PC WORD" in page.locator("#main").inner_text()
                assert page.get_by_label("PC WORD",exact=True).input_value()=="0xBEEF"
                page.screenshot(path=str(ARTIFACTS/f"areas-{width}.png"),full_page=True)
                page.get_by_label("Area data",exact=True).select_option("render")
                page.get_by_label("UNKNOWN EFFECT BIT",exact=True).wait_for()
                assert page.get_by_label("UNKNOWN EFFECT BIT",exact=True).input_value()=="Set"
                assert page.get_by_label("DIMENSION / MODE BYTE",exact=True).input_value()=="0x00"
                page.get_by_label("L2 X SPEED",exact=True).select_option("7")
                page.get_by_label("L2 Y SPEED",exact=True).select_option("15")
                page.get_by_label("LAYER 1 MAIN",exact=True).check()
                page.get_by_label("LAYER 2 MAIN",exact=True).uncheck()
                page.get_by_label("LAYER 1 EFFECT",exact=True).uncheck()
                page.wait_for_function("!document.querySelector('#global-save')?.disabled")
                page.locator("#global-save").click()
                page.wait_for_function("document.querySelector('#global-save')?.disabled")
                assert page.evaluate("window.__posts.some(value=>value.path==='/api/scene-render-settings/save')")
                assert page.get_by_label("UNKNOWN EFFECT BIT",exact=True).input_value()=="Set"
                page.screenshot(path=str(ARTIFACTS/f"area-render-{width}.png"),full_page=True)
                page.get_by_label("Area data",exact=True).select_option("map")
                page.get_by_label("TILE INDEX",exact=True).wait_for()
                assert page.get_by_label("BANK",exact=True).input_value()=="Upper · 256-511"
                assert page.get_by_label("PROPERTY BYTES",exact=True).input_value()=="7"
                assert page.get_by_label("SCREEN FLAGS",exact=True).input_value()=="0x5A"
                page.get_by_label("TILE INDEX",exact=True).fill("300")
                page.wait_for_function("!document.querySelector('#global-save')?.disabled")
                page.locator("#global-save").click()
                page.wait_for_function("document.querySelector('#global-save')?.disabled")
                assert page.evaluate("window.__posts.some(value=>value.path==='/api/scene-map/save')")
                assert page.get_by_label("TILE INDEX",exact=True).input_value()=="300"
                page.screenshot(path=str(ARTIFACTS/f"area-map-{width}.png"),full_page=True)
                page.get_by_label("Area data",exact=True).select_option("properties")
                page.get_by_label("REPEAT COUNT",exact=True).wait_for()
                page.locator(".lex-column-list-row",has_text="255").first.click()
                assert page.get_by_label("REPEAT COUNT",exact=True).input_value()=="255"
                assert page.get_by_label("COMPRESSED",exact=True).input_value()=="Yes"
                assert page.get_by_label("UNKNOWN BYTE 2 BIT 5",exact=True).input_value()=="Set"
                assert page.get_by_label("UNKNOWN BYTE 3 BIT 4",exact=True).input_value()=="Set"
                page.get_by_label("COLLISION",exact=True).select_option("30")
                page.get_by_label("MOVE DIRECTION",exact=True).select_option("3")
                page.get_by_label("MOVE SPEED",exact=True).fill("2")
                page.get_by_label("TOP ABOVE ALL",exact=True).check()
                page.get_by_label("NPC COLLISION",exact=True).check()
                page.wait_for_function("!document.querySelector('#global-save')?.disabled")
                page.locator("#global-save").click()
                page.wait_for_function("document.querySelector('#global-save')?.disabled")
                assert page.evaluate("window.__posts.some(value=>value.path==='/api/scene-properties/save')")
                assert page.get_by_label("REPEAT COUNT",exact=True).input_value()=="255"
                assert page.get_by_label("UNKNOWN BYTE 2 BIT 5",exact=True).input_value()=="Set"
                page.screenshot(path=str(ARTIFACTS/f"area-properties-{width}.png"),full_page=True)

                page.locator(".lex-tab-label-text",has_text="Worlds").click()
                page.locator("#main").get_by_text("PALETTE ANIMATION BYTE", exact=True).wait_for()
                assert "World 0" in page.locator("#main").inner_text()
                assert page.get_by_label("BYTE OFFSET",exact=True).input_value()=="0xFD10"
                page.get_by_label("MAP",exact=True).fill("42")
                page.wait_for_function("!document.querySelector('#global-save')?.disabled")
                page.locator("#global-save").click()
                page.wait_for_function("document.querySelector('#global-save')?.disabled")
                assert page.evaluate("window.__posts.some(value=>value.path==='/api/worlds/save')")
                assert page.get_by_label("MAP",exact=True).input_value()=="42"
                page.screenshot(path=str(ARTIFACTS/f"worlds-{width}.png"),full_page=True)
                page.get_by_label("World data",exact=True).wait_for()

                page.get_by_label("World data",exact=True).select_option("map")
                page.get_by_label("TILE INDEX",exact=True).wait_for()
                assert page.get_by_label("TRAILING BYTES",exact=True).input_value()=="1"
                page.get_by_label("TILE INDEX",exact=True).fill("9")
                page.wait_for_function("!document.querySelector('#global-save')?.disabled")
                page.locator("#global-save").click()
                page.wait_for_function("window.__posts.some(value=>value.path==='/api/world-map/save')")
                page.get_by_label("World data",exact=True).wait_for()
                assert page.get_by_label("TILE INDEX",exact=True).input_value()=="9"
                page.screenshot(path=str(ARTIFACTS/f"world-map-{width}.png"),full_page=True)

                page.get_by_label("World data",exact=True).select_option("properties")
                page.get_by_label("TOP LEFT",exact=True).wait_for()
                page.get_by_label("TOP LEFT",exact=True).select_option("4")
                page.wait_for_function("!document.querySelector('#global-save')?.disabled")
                page.locator("#global-save").click()
                page.wait_for_function("window.__posts.some(value=>value.path==='/api/world-properties/save')")
                page.get_by_label("World data",exact=True).wait_for()
                assert page.get_by_label("TOP RIGHT",exact=True).input_value()=="2"
                page.screenshot(path=str(ARTIFACTS/f"world-properties-{width}.png"),full_page=True)

                page.get_by_label("World data",exact=True).select_option("music")
                page.get_by_label("RIGHT MUSIC",exact=True).wait_for()
                page.get_by_label("RIGHT MUSIC",exact=True).fill("9")
                page.wait_for_function("!document.querySelector('#global-save')?.disabled")
                page.locator("#global-save").click()
                page.wait_for_function("window.__posts.some(value=>value.path==='/api/world-music/save')")
                page.get_by_label("World data",exact=True).wait_for()
                assert page.get_by_label("LEFT MUSIC",exact=True).input_value()=="10"
                page.screenshot(path=str(ARTIFACTS/f"world-music-{width}.png"),full_page=True)

                page.get_by_label("World data",exact=True).select_option("colors")
                world_color=page.locator('#main input[type="color"]').first
                world_color.wait_for()
                assert page.get_by_label("BIT 15",exact=True).input_value()=="Set"
                world_color.fill("#00ff00")
                page.wait_for_function("!document.querySelector('#global-save')?.disabled")
                page.locator("#global-save").click()
                page.wait_for_function("window.__posts.some(value=>value.path==='/api/world-colors/save')")
                page.get_by_label("World data",exact=True).wait_for()
                assert page.get_by_label("BIT 15",exact=True).input_value()=="Set"
                page.screenshot(path=str(ARTIFACTS/f"world-colors-{width}.png"),full_page=True)

                page.locator(".lex-tab-label-text",has_text="World Exits").click()
                page.locator("#main").get_by_text("Y FLAG BITS", exact=True).wait_for()
                assert "Truce Canyon" in page.locator("#main").inner_text()
                assert page.get_by_label("Y FLAG BITS",exact=True).input_value()=="0xC0"
                assert page.get_by_label("FACING FLAG BITS",exact=True).input_value()=="0xA1"
                page.get_by_label("SCENE",exact=True).fill("33")
                page.wait_for_function("!document.querySelector('#global-save')?.disabled")
                page.locator("#global-save").click()
                page.wait_for_function("document.querySelector('#global-save')?.disabled")
                assert page.evaluate("window.__posts.some(value=>value.path==='/api/world-navigation/save')")
                assert page.get_by_label("SCENE",exact=True).input_value()=="33"
                page.screenshot(path=str(ARTIFACTS/f"world-exits-{width}.png"),full_page=True)
                page.locator(".lex-column-list-row",has_text="trigger").first.click()
                page.get_by_label("SCRIPT ADDRESS",exact=True).fill("1")
                page.wait_for_function("!document.querySelector('#global-save')?.disabled")
                page.locator("#global-save").click()
                page.wait_for_function("document.querySelector('#global-save')?.disabled")
                assert page.get_by_label("SCRIPT ADDRESS",exact=True).input_value()=="1"
                page.screenshot(path=str(ARTIFACTS/f"world-triggers-{width}.png"),full_page=True)

                page.locator(".lex-tab-label-text",has_text="Tiles").click()
                page.locator("#main").get_by_text("FRAME 0 LOW BITS", exact=True).wait_for()
                assert page.get_by_label("FRAME 0 LOW BITS",exact=True).input_value()=="0xA"
                assert page.get_by_label("TRAILING BYTES",exact=True).input_value()=="1"
                page.get_by_label("DESTINATION CHIP",exact=True).fill("7")
                page.get_by_label("FRAME 0 DURATION",exact=True).select_option("32")
                page.get_by_label("FRAME 1 SOURCE CHIP",exact=True).fill("9")
                page.wait_for_function("!document.querySelector('#global-save')?.disabled")
                page.locator("#global-save").click()
                page.wait_for_function("document.querySelector('#global-save')?.disabled")
                assert page.evaluate("window.__posts.some(value=>value.path==='/api/chip-animations/save')")
                assert page.get_by_label("DESTINATION CHIP",exact=True).input_value()=="7"
                assert page.get_by_label("FRAME 0 LOW BITS",exact=True).input_value()=="0xA"
                page.screenshot(path=str(ARTIFACTS/f"tile-animations-{width}.png"),full_page=True)
                page.get_by_label("Tile data",exact=True).wait_for()

                page.get_by_label("Tile data",exact=True).select_option("tilesets")
                page.get_by_label("GRAPHICS SET 0",exact=True).wait_for()
                assert page.get_by_label("GRAPHICS SET 7",exact=True).input_value()=="255"
                assert page.get_by_label("TRAILING BYTES",exact=True).input_value()=="1"
                page.get_by_label("GRAPHICS SET 0",exact=True).fill("9")
                page.wait_for_function("!document.querySelector('#global-save')?.disabled")
                page.locator("#global-save").click()
                page.wait_for_function("document.querySelector('#global-save')?.disabled")
                assert page.evaluate("window.__posts.some(value=>value.path==='/api/graphics-sets/save')")
                assert page.get_by_label("GRAPHICS SET 0",exact=True).input_value()=="9"
                page.screenshot(path=str(ARTIFACTS/f"tile-graphics-sets-{width}.png"),full_page=True)
                page.get_by_label("Tile data",exact=True).wait_for()

                page.get_by_label("Tile data",exact=True).select_option("assemblies")
                page.get_by_label("UNKNOWN PRIORITY BITS",exact=True).wait_for()
                assert page.get_by_label("UNKNOWN PRIORITY BITS",exact=True).input_value()=="0xA0"
                assert page.get_by_label("TRAILING BYTES",exact=True).input_value()=="1"
                page.get_by_label("CHIP INDEX",exact=True).fill("511")
                page.get_by_label("PALETTE",exact=True).fill("6")
                page.get_by_label("FLIP HORIZONTAL",exact=True).uncheck()
                page.get_by_label("FLIP VERTICAL",exact=True).check()
                page.get_by_label("PRIORITY",exact=True).uncheck()
                page.wait_for_function("!document.querySelector('#global-save')?.disabled")
                page.locator("#global-save").click()
                page.wait_for_function("document.querySelector('#global-save')?.disabled")
                assert page.evaluate("window.__posts.some(value=>value.path==='/api/tile-assemblies/save')")
                assert page.get_by_label("CHIP INDEX",exact=True).input_value()=="511"
                assert page.get_by_label("UNKNOWN PRIORITY BITS",exact=True).input_value()=="0xA0"
                page.screenshot(path=str(ARTIFACTS/f"tile-assemblies-{width}.png"),full_page=True)
                page.get_by_label("Tile data",exact=True).select_option("sprites")
                page.get_by_label("UNKNOWN SIZE FLAGS",exact=True).wait_for()
                assert page.get_by_label("STORED BITMAP",exact=True).input_value()=="9"
                assert page.get_by_label("UNKNOWN SIZE FLAGS",exact=True).input_value()=="0xA4"
                assert page.get_by_label("UNKNOWN FLAGS",exact=True).input_value()=="0xD2"
                assert page.get_by_label("ENEMY UNKNOWN 1",exact=True).input_value()=="0x11"
                page.get_by_label("SIZE GROUP CODE",exact=True).fill("2")
                page.get_by_label("PRIMARY ENEMY",exact=True).uncheck()
                page.get_by_label("ANIMATION SET",exact=True).fill("9")
                page.get_by_label("HAND X",exact=True).fill("-8")
                page.get_by_label("HAND Y",exact=True).fill("12")
                page.wait_for_function("!document.querySelector('#global-save')?.disabled")
                page.locator("#global-save").click()
                page.wait_for_function("document.querySelector('#global-save')?.disabled")
                assert page.evaluate("window.__posts.some(value=>value.path==='/api/sprite-headers/save')")
                assert page.get_by_label("UNKNOWN SIZE FLAGS",exact=True).input_value()=="0xA4"
                assert page.get_by_label("ANIMATION SET",exact=True).input_value()=="9"
                page.screenshot(path=str(ARTIFACTS/f"sprite-descriptors-{width}.png"),full_page=True)
                page.get_by_label("Tile data",exact=True).select_option("spriteassemblies")
                page.get_by_label("ODD SOURCE BIT",exact=True).wait_for()
                assert page.get_by_label("ODD SOURCE BIT",exact=True).input_value()=="Set"
                assert page.get_by_label("UNKNOWN FLAGS",exact=True).input_value()=="0xA0"
                assert page.get_by_label("HEADER WORD",exact=True).input_value()=="0xBEEF"
                assert page.get_by_label("PREFIX",exact=True).input_value()=="AABBCC"
                page.get_by_label("CHIP INDEX",exact=True).fill("511")
                page.get_by_label("X OFFSET",exact=True).fill("7")
                page.get_by_label("Y OFFSET",exact=True).fill("-10")
                page.get_by_label("FLIP HORIZONTAL",exact=True).uncheck()
                page.wait_for_function("!document.querySelector('#global-save')?.disabled")
                page.locator("#global-save").click()
                page.wait_for_function("document.querySelector('#global-save')?.disabled")
                assert page.evaluate("window.__posts.some(value=>value.path==='/api/sprite-assemblies/save')")
                assert page.get_by_label("ODD SOURCE BIT",exact=True).input_value()=="Set"
                assert page.get_by_label("UNKNOWN FLAGS",exact=True).input_value()=="0xA0"
                assert page.get_by_label("CHIP INDEX",exact=True).input_value()=="511"
                page.screenshot(path=str(ARTIFACTS/f"sprite-assemblies-{width}.png"),full_page=True)

                page.locator(".lex-tab-label-text",has_text="Area Exits").click()
                page.locator("#main").get_by_text("PRESERVED BITS", exact=True).wait_for()
                assert "PRESERVED BITS" in page.locator("#main").inner_text()
                assert page.get_by_label("PRESERVED BITS",exact=True).input_value()=="0xA0"
                page.screenshot(path=str(ARTIFACTS/f"exits-{width}.png"),full_page=True)

                page.locator(".lex-tab-label-text",has_text="Treasure").click()
                page.locator("#main").get_by_text("PRESERVED WORD", exact=True).wait_for()
                assert "Ruby Vest" in page.locator("#main").inner_text()
                assert page.get_by_label("PRESERVED WORD",exact=True).input_value()=="0xCAFE"
                page.screenshot(path=str(ARTIFACTS/f"treasure-{width}.png"),full_page=True)

                page.locator(".lex-tab-label-text",has_text="Palettes").click()
                page.locator('input[type="color"]').wait_for()
                assert page.locator('input[type="color"]').count()==1
                assert "BIT 15" in page.locator("#main").inner_text()
                page.screenshot(path=str(ARTIFACTS/f"palettes-{width}.png"),full_page=True)

                page.locator("#plugin-data-map").click()
                page.locator(".lex-data-map-table").wait_for()
                assert page.locator(".lex-data-map-table").count()==1
                page.get_by_label("Search the data map",exact=True).fill("Area settings")
                area_settings_row=page.locator(".lex-column-list-row",has_text="Area settings").first
                area_settings_row.wait_for()
                assert area_settings_row.get_by_label("Integrated",exact=True).count()==1
                layout=metrics(page)
                assert layout["bodyHeight"]<=height+2,layout
                assert layout["mainBottom"]<=height+2,layout
                assert layout["bodyWidth"]<=width+2,layout
                page.screenshot(path=str(ARTIFACTS/f"datamap-{width}.png"),full_page=True)
                results.append({
                    "cssWidth": width, "cssHeight": height,
                    "deviceScaleFactor": scale,
                    "physicalEquivalent": [round(width * scale), round(height * scale)],
                    "label": shot, "metrics": layout, "status": "passed",
                })
                page.close()
        finally:
            browser.close()
    (ARTIFACTS/"results.json").write_text(json.dumps({"fixtureOnly":True,"results":results,"errors":errors},indent=2),encoding="utf-8")
    assert not errors,errors
    print(json.dumps(results,indent=2))


if __name__=="__main__":
    main()
