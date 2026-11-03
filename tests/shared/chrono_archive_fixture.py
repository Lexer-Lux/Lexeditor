"""Authored Chrono Trigger resources for real-service UI audits; no game data."""
import struct
from pathlib import Path

from plugins.chrono_trigger.plugin import _fixture_archive
from plugins.chrono_trigger.world_data import BANK_PATH, HEADER_OFFSET, HEADER_SIZE, WORLD_COUNT


def create_game(game: Path) -> None:
    game.mkdir(parents=True, exist_ok=True)
    (game / "Chrono Trigger.exe").write_bytes(b"authored fixture; not executable")
    exits_offset = struct.pack("<IHH", 2, 0, 1)
    exits_data = b"HEAD" + struct.pack("<BBBBHBB", 2, 3, 1, 0xA5, 7, 8, 9)
    treasure_offset = struct.pack("<IHH", 2, 0, 1)
    treasure_data = b"HEAD" + struct.pack("<BBHH", 4, 5, 0x1002, 0xCAFE)
    scene_header = struct.pack("<10H4B", 10, 1, 2, 3, 4, 5, 6, 7, 8, 0xBEEF, 0, 1, 14, 15) + b"\xAA\xBB"
    palette = b"\x12\x34" + struct.pack("<H", 0x801F) + (b"\x00\x00" * 255) + b"\xCC"
    world_bank = bytearray(b"\xA5" * (HEADER_OFFSET + WORLD_COUNT * HEADER_SIZE + 3))
    world_bank[HEADER_OFFSET:HEADER_OFFSET + HEADER_SIZE] = bytes(range(HEADER_SIZE))
    scene_map = bytearray(bytes([0, 0, 0x21, 0x43, 0x5A, 0xCB]) + bytes(16 * 16 * 2))
    scene_map[6] = 3
    scene_map[6 + 16 * 16] = 4
    scene_map.extend(bytes([0x01, 0, 0, 0x80, 0x20, 0x10, 255]))
    sprite_descriptor = bytes([9, 8, 7, 0xAC, 5, 0xD2, 0xFE, 0x03, 0x11, 0x22, 0x33, 0xEE])
    sprite_cell = bytearray(b"\xAA\xBB\xCC" + struct.pack("<HH", 2, 0xBEEF))
    sprite_cell.extend(bytes([2]))
    sprite_cell.extend(struct.pack("<HbbB", 0x025C, -5, -25, 0xA1))
    sprite_cell.extend(struct.pack("<HbbB", 0x0000, 1, 2, 0x02))
    sprite_cell.extend(bytes([1]))
    sprite_cell.extend(struct.pack("<HbbB", 0x0020, 3, 4, 0x80))
    sprite_cell.extend(b"\xEE")
    graphics_sets = bytes([1, 2, 3, 4, 5, 6, 7, 0xFF]) + b"\xDD"
    assembly_l12 = bytearray(512 * 4 * 3 + 1)
    struct.pack_into("<HB", assembly_l12, 0, 300 | 0x0400 | (5 << 12), 0xA1)
    assembly_l12[-1] = 0xCC
    assembly_l3 = bytearray(256 * 4 * 3)
    struct.pack_into("<HB", assembly_l3, 0, 77 | 0x0800 | (3 << 12), 0x41)
    chip_animation = (
        bytes([2, 2]) + struct.pack("<H", 64) + bytes([0x1A, 0x4B])
        + struct.pack("<HH", 96, 128)
        + bytes([1]) + struct.pack("<H", 160) + bytes([0x80]) + struct.pack("<H", 192)
        + b"\xEE"
    )
    world_map = bytearray(96 * 64 * 2 + 1)
    world_map[0] = 3
    world_map[96 * 64] = 4
    world_map[-1] = 0xFA
    world_props = bytearray(512 + 1)
    world_props[0:2] = b"\x12\x34"
    world_props[-1] = 0xFB
    world_music = bytearray((96 * 64 // 2) + 1)
    world_music[0] = 0xA5
    world_music[-1] = 0xFC
    world_colors = struct.pack("<HHH", 0x801F, 0x03E0, 0x7C00) + b"\xFD"
    world_event = (
        bytes([2])
        + struct.pack("<BBBHBBB", 0x85, 0xC7, 0, 12, 0xAD, 9, 10)
        + struct.pack("<BBBHBBB", 0x82, 3, 1, 0x1FF, 0x52, 0, 0)
        + bytes([2, 0x84, 5, 0, 0, 0, 0])
        + bytes([1, 7, 8, 9])
        + bytes([2]) + struct.pack("<HH", 0x400, 0x410)
        + b"\xAA\xBB"
    )
    _fixture_archive(game / "resources.bin", [
        ("Localize/en/msg/item.txt", b"0000,Sword\r\n0001,Armor\r\n0002,Mail\r\n"),
        ("Localize/en/msg/cmes0.txt", b"FLD_001,Hello\r\nFLD_002,World\r\n"),
        ("Localize/en/msg/debug_map.txt", b"0000,Millennial Fair\r\n"),
        ("Localize/en/msg/w_map.txt", b"0000,Truce Canyon\r\n0001,Medina\r\n"),
        ("Game/world/Map/Map_0000.dat", bytes(world_map)),
        ("Game/world/Id/Id_0000.dat", bytes(world_props)),
        ("Game/world/SeId/SeId_0000.dat", bytes(world_music)),
        ("Game/world/colanim_bin/0_colanim.bin", world_colors),
        ("Game/world/EventTable/EventTable_0004.dat", world_event),
        ("Game/chara/dat/c005.dat", sprite_descriptor),
        ("Game/chara/cell/c005.cel", bytes(sprite_cell)),
        ("Game/field/MapTable/MapTable_0006.dat", bytes(scene_map)),
        ("Game/field/BGSetTable/bgsettable_4.dat", graphics_sets),
        ("Game/field/ChipTable/ChipTable_0004.dat", bytes(assembly_l12)),
        ("Game/field/ChipTable/ChipTableBg3_0002.dat", bytes(assembly_l3)),
        ("Game/field/BGAnime/bganimeinfo_4.dat", chip_animation),
        ("Game/field/Mapinfo/mapinfo_1.dat", scene_header),
        ("Game/field/palette_bin/plt4.bin", palette),
        ("Game/common/MapJumpOffsetTbl.dat", exits_offset),
        ("Game/common/MapJumpDataTbl.dat", exits_data),
        ("Game/common/TakaraOffsetTbl.dat", treasure_offset),
        ("Game/common/TakaraDataTbl.dat", treasure_data),
        (BANK_PATH, bytes(world_bank)),
    ])

