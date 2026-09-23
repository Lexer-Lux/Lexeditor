"""Synthetic editor fixtures only; these are not game assets or runtime tests."""
from pathlib import Path
import struct
import json
from contextlib import ExitStack, contextmanager
from unittest.mock import patch


def loot_document():
    return {
        "schemaVersion": 1, "contract": "LexerRDR.loot",
        "source": {"archive": "synthetic fixture", "script": "not a game script", "functions": []},
        "corpseBonusItem": {"chancePercent": 10, "entries": [
            {"itemEnum": i, "quantity": 1, "weight": 1} for i in (1, 2, 6, 7, 8)]},
        "money": {"baseRoll": {"range": {"minimum": 0, "maximum": 2},
                  "applyStatScale": True, "applyItem17Multiplier": True, "applyFinalMultiplier": True},
                  "decoratorPaths": [
                      {"decorator": "NoMoney", "operation": "suppress"},
                      {"decorator": "iAdditionalMoney", "operation": "base-plus-decorator"},
                      {"decorator": "nOnlyMoney", "operation": "decorator-only"}]}}


def shop_bytes():
    data = bytearray(4096)
    values = {
        16: 0x50000080, 20: 0x00010001, 24: 0x50000084, 28: 0x00010001,
        0x80: 0x12345678, 0x84: 0x50000100, 0x88: 0x50000160, 0x8C: 0x50000180,
        0x90: 0x500001C0, 0x94: 0x500001CC, 0x98: 0x500001D8, 0x9C: 0x500001EC,
        0x120: 0x50000300, 0x128: 0x50000088, 0x12C: 0x00010001,
        0x160: 0xD6F7F3F1, 0x168: 0x1C51E604, 0x170: 0x5000008C, 0x174: 0x00010001,
        0x180: 0xB16C14A8, 0x190: 0x50000090, 0x194: 0x00040004,
        0x1C0: 0x3EED2FB8, 0x1C4: 0xDE02D359, 0x1C8: 0x50000380,
        0x1CC: 0x178DF99A, 0x1D0: 0x65E7F789,
        0x1D8: 0x7EB41668, 0x1DC: 0x7EBD2697, 0x1E4: 2,
        0x1EC: 0x7EB41668, 0x1F0: 0x7992CBA6, 0x1F8: 10,
    }
    for offset, value in values.items():
        struct.pack_into('<I', data, offset, value)
    struct.pack_into('<f', data, 0x1D4, 1.25)
    script = b'content\\scripting\\gringo\\GringoBrains\\GringoBrainScripts\\Shopkeeper_Brain\0'
    item = b'ITEM_TEST_SHOP\0'
    data[0x300:0x300 + len(script)] = script
    data[0x380:0x380 + len(item)] = item
    return bytes(data)


def _joaat(value: str) -> int:
    result = 0
    for byte in value.lower().encode("ascii"):
        result = (result + byte) & 0xFFFFFFFF
        result = (result + (result << 10)) & 0xFFFFFFFF
        result ^= result >> 6
    result = (result + (result << 3)) & 0xFFFFFFFF
    result ^= result >> 11
    result = (result + (result << 15)) & 0xFFFFFFFF
    return result & 0xFFFFFFFF


def string_table_bytes():
    """Small ordinary PC STRTBL with one shared language block."""
    identifiers = ("HELLO", "GOODBYE")
    prefix = bytearray(struct.pack("<i", 11) + bytes(44))
    prefix += struct.pack("<Ii", 256, len(identifiers))
    for identifier in identifiers:
        raw = identifier.encode("ascii")
        prefix += struct.pack("<I", len(raw)) + raw + b"\0"

    def entry(identifier, text):
        entry_hash = _joaat(identifier)
        encoded = (text + "\0").encode("utf-16le")
        return (
            struct.pack("<I6B", entry_hash, 1, 2, 3, 4, 5, 6)
            + struct.pack("<i", len(encoded) // 2)
            + encoded
            + struct.pack("<ffBB", 1.0, 1.0, 0, 0)
        )

    english = struct.pack("<I", 2) + entry("HELLO", "Hello") + entry("GOODBYE", "Goodbye")
    spanish = struct.pack("<I", 2) + entry("HELLO", "Hola") + entry("GOODBYE", "Adiós")
    english_offset = len(prefix)
    spanish_offset = english_offset + len(english)
    positions = [english_offset] + [0] * 8 + [spanish_offset, spanish_offset]
    for index, offset in enumerate(positions):
        struct.pack_into("<I", prefix, 4 + index * 4, offset)
    return bytes(prefix) + english + spanish


def rbf_bytes():
    """Synthetic RBF0 fixture with only publicly documented record shapes."""
    def record(index, kind, name=None, payload=b""):
        result = bytearray([index, kind])
        if name is not None:
            raw = name.encode("ascii")
            result += struct.pack("<h", len(raw)) + raw
        result += payload
        return bytes(result)
    data = bytearray(b"RBF0")
    data += record(0, 0x00, "Tuning", struct.pack("<hhh", 0, 0, 1))
    data += record(1, 0x10, "Version", struct.pack("<I", 1))
    data += record(2, 0x40, "Scale", struct.pack("<f", 1.0))
    data += record(3, 0x30, "Enabled")
    data += record(4, 0x60, "Label", struct.pack("<h", 7) + b"Fixture")
    data += b"\xff\xff"
    return bytes(data)


def fake_resource_tool(args, **_kwargs):
    """Identity codec for testing save ordering, not the real RSC85 compressor."""
    if args[0] == "resource-pack":
        Path(args[3]).write_bytes(b"fixture:" + Path(args[2]).read_bytes())
    elif args[0] == "resource-unpack":
        data = Path(args[1]).read_bytes()
        if not data.startswith(b"fixture:"):
            raise ValueError("Invalid synthetic resource")
        Path(args[2]).write_bytes(data[len(b"fixture:"):])
    else:
        raise AssertionError(args)


@contextmanager
def workspace(root: Path, count=1):
    from plugins.rdr import server, mission_rewards
    project, mod, data, game = root / "project", root / "project/mod", root / "data", root / "game"
    mapping = {
        "PROJECT": project, "MOD_ROOT": mod, "GAME_ROOT": game, "EXTRACT_ROOT": data,
        "PREPARED_ROOT": data / "tune_d11generic", "OVERRIDE_ROOT": mod / "tune_d11generic",
        "CONTENT_PREPARED_ROOT": data / "content", "CONTENT_OVERRIDE_ROOT": mod / "content",
        "GRINGO_PACKED_ROOT": data / "gringores", "GRINGO_UNPACKED_ROOT": data / "gringores-unpacked",
        "GRINGO_OVERRIDE_ROOT": mod / "gringores", "SETTINGS_FILE": project / "LexerRDR.ini",
        "LOOT_FILE": project / "LexerRDR.loot.json",
        "DATA_MAP_FILE": root / "data_map.generated.json",
        "MISSION_TEST_STATE": project / ".lexeditor-mission-test.json"}
    for key, path in mapping.items():
        if key.endswith("FILE") or key.endswith("STATE"):
            path.parent.mkdir(parents=True, exist_ok=True)
        else:
            path.mkdir(parents=True, exist_ok=True)
    inv = mapping["CONTENT_PREPARED_ROOT"] / "content/init/inventory/inventory.xml"
    inv.parent.mkdir(parents=True)
    rows = ''.join(f'<Item type="invGringoType"><Name content="ascii">TEST_{i}</Name>'
        f'<FriendlyName content="ascii">Test item {i:03}</FriendlyName><MaxItemCount value="5"/>'
        '<HUDReticleIndex value="0"/><SpawnTimeOut value="0"/><Enabled value="true"/>'
        '<mp_EquipStringId content="ascii">EQUIP</mp_EquipStringId>'
        '<Unsupported keep="yes"><Nested value="untouched"/></Unsupported></Item>' for i in range(count))
    inv.write_text(f'<invManager><Types><!--keep-comment-->{rows}</Types></invManager>')
    (inv.parent / "dlc_inventory.xml").write_text('<invManagerDLC><Types/></invManagerDLC>')
    tuning = mapping["PREPARED_ROOT"] / "tune/ai/motives.xml"
    tuning.parent.mkdir(parents=True)
    tuning.write_text('<motives><value>vanilla</value></motives>')
    tuning_rbf = mapping["PREPARED_ROOT"] / "tune/ai/protected.tune"
    tuning_rbf.write_bytes(rbf_bytes())
    tuning_strings = mapping["PREPARED_ROOT"] / "tune/stringtable/global.strtbl"
    tuning_strings.parent.mkdir(parents=True)
    tuning_strings.write_bytes(string_table_bytes())
    content_strings = (
        mapping["CONTENT_PREPARED_ROOT"]
        / "content/dlc/zombiepack/zombiepack_standalone.strtbl"
    )
    content_strings.parent.mkdir(parents=True)
    content_strings.write_bytes(string_table_bytes())
    ps3_strings = content_strings.with_name("zombiepack_standalone_ps3.strtbl")
    ps3_strings.write_bytes(string_table_bytes())
    for i in range(count):
        for key, data_bytes in (("GRINGO_UNPACKED_ROOT", shop_bytes()),
                                ("GRINGO_PACKED_ROOT", b"fixture:" + shop_bytes())):
            target = mapping[key] / f"gringores/smoke_{i:03}.wgd"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data_bytes)
    mapping["SETTINGS_FILE"].write_bytes(
        b"; keep comment\r\n[WeaponRadial]\r\nEnabled=false\r\n"
        b"TimeScale = 0.25 ; keep inline\r\nUnknownKey=keep\r\n"
        b"[DevelopmentCamera]\r\nMoveSpeed=5\r\nRotationSpeed=90\r\n")
    mapping["LOOT_FILE"].write_text(json.dumps(loot_document()))
    for filename in ("RedHook.dll", "winmm.dll"):
        (game / filename).write_bytes(b"synthetic fixture, not executable")
    (game / "RedHook.ini").write_text('[RedHook]\nSkipIntroLogos=true\n')
    with ExitStack() as stack:
        for key, value in mapping.items():
            stack.enter_context(patch.object(server, key, value))
        stack.enter_context(patch.object(server, "STRING_TABLE_SOURCES", {
            "tuning": {
                "label": "Tuning",
                "prepared": mapping["PREPARED_ROOT"],
                "project": mapping["OVERRIDE_ROOT"],
                "prefix": "tune",
            },
            "content": {
                "label": "Content",
                "prepared": mapping["CONTENT_PREPARED_ROOT"],
                "project": mapping["CONTENT_OVERRIDE_ROOT"],
                "prefix": "content",
            },
        }))
        stack.enter_context(patch.object(server, "_run_resource_tool", fake_resource_tool))
        stack.enter_context(patch.object(mission_rewards, "OVERRIDE_FILE", project / "LexerRDR.missions.json"))
        yield mapping