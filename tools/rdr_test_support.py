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
    from games.rdr import server, mission_rewards
    project, mod, data, game = root / "project", root / "project/mod", root / "data", root / "game"
    mapping = {
        "PROJECT": project, "MOD_ROOT": mod, "GAME_ROOT": game, "EXTRACT_ROOT": data,
        "PREPARED_ROOT": data / "tune_d11generic", "OVERRIDE_ROOT": mod / "tune_d11generic",
        "CONTENT_PREPARED_ROOT": data / "content", "CONTENT_OVERRIDE_ROOT": mod / "content",
        "GRINGO_PACKED_ROOT": data / "gringores", "GRINGO_UNPACKED_ROOT": data / "gringores-unpacked",
        "GRINGO_OVERRIDE_ROOT": mod / "gringores", "SETTINGS_FILE": project / "LexerRDR.ini",
        "LOOT_FILE": project / "LexerRDR.loot.json"}
    for key, path in mapping.items():
        if key.endswith("FILE"):
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
        stack.enter_context(patch.object(server, "_run_resource_tool", fake_resource_tool))
        stack.enter_context(patch.object(mission_rewards, "OVERRIDE_FILE", project / "LexerRDR.missions.json"))
        yield mapping
