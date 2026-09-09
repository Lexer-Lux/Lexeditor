"""Semantic annotations for proven Chrono Trigger Steam field-event commands.

Only argument meanings directly established by the PC command definitions are
annotated here. Raw bytes remain authoritative. A separate fixed-width editor
layer may write a subset of these fields without changing command boundaries.
"""

from __future__ import annotations


SCRIPT_MEM_START = 0x7F0200

BATTLE_FLAGS = (
    (0, 0x01, "no win pose"),
    (0, 0x02, "bottom menu"),
    (0, 0x04, "small PC solidity"),
    (0, 0x08, "unknown 1:08"),
    (0, 0x10, "static enemies"),
    (0, 0x20, "special event"),
    (0, 0x40, "unknown 1:40"),
    (0, 0x80, "no run"),
    (1, 0x01, "unknown 2:01"),
    (1, 0x02, "unknown 2:02"),
    (1, 0x04, "unknown 2:04"),
    (1, 0x08, "unknown 2:08"),
    (1, 0x10, "unknown 2:10"),
    (1, 0x20, "no game over"),
    (1, 0x40, "map music"),
    (1, 0x80, "regroup"),
)

FACING_NAMES = ("up", "down", "left", "right")


def _u16(data: bytes, offset: int = 0) -> int:
    return int.from_bytes(data[offset:offset + 2], "little")


def _script_address(offset: int) -> int:
    return SCRIPT_MEM_START + int(offset) * 2


def _lookup(values: list[str], index: int, prefix: str) -> str:
    return values[index] if 0 <= index < len(values) and values[index].strip() else f"{prefix} {index}"


def command_semantics(command: dict, labels: dict) -> dict | None:
    opcode = int(command["opcode"])
    try:
        args = bytes.fromhex(command.get("argumentsHex", ""))
    except ValueError:
        return None
    scenes = labels.get("sceneNames", [])
    items = labels.get("itemNames", [])
    players = labels.get("playerNames", [])

    if opcode in {0x20, 0x55, 0x7F} and len(args) == 1:
        address = _script_address(args[0])
        label = {
            0x20: "PC1 ID",
            0x55: "Storyline counter",
            0x7F: "Random value",
        }[opcode]
        return {"summary": f"{label} → 0x{address:06X}", "storeAddress": address}
    if opcode == 0x83 and len(args) == 3:
        enemy = _u16(args)
        return {
            "summary": f"Enemy {enemy} · slot {args[2] & 0x7F} · {'static' if args[2] & 0x80 else 'dynamic'}",
            "enemyId": enemy, "slot": args[2] & 0x7F, "static": bool(args[2] & 0x80),
            "slotFlags": args[2],
        }
    if opcode == 0x87 and len(args) == 1 and args[0] <= 0x80:
        return {"summary": f"Script speed {args[0]}", "scriptSpeed": args[0]}
    if opcode == 0x89 and len(args) == 1:
        return {"summary": f"NPC movement speed {args[0]}", "movementSpeed": args[0]}
    if opcode == 0x8A and len(args) == 1:
        address = _script_address(args[0])
        return {"summary": f"NPC speed from 0x{address:06X}", "speedAddress": address}
    if opcode == 0x8B and len(args) == 2:
        return {"summary": f"NPC tile position ({args[0]}, {args[1]})", "tileX": args[0], "tileY": args[1]}
    if opcode == 0x8C and len(args) == 2:
        x_address, y_address = _script_address(args[0]), _script_address(args[1])
        return {
            "summary": f"NPC position from X 0x{x_address:06X} · Y 0x{y_address:06X}",
            "xAddress": x_address, "yAddress": y_address,
        }
    if opcode == 0xA6 and len(args) == 1 and args[0] <= 3:
        return {"summary": f"NPC facing {FACING_NAMES[args[0]]}", "facing": args[0], "facingName": FACING_NAMES[args[0]]}
    if opcode == 0xA7 and len(args) == 1:
        address = _script_address(args[0])
        return {"summary": f"NPC facing from 0x{address:06X}", "facingAddress": address}
    if opcode == 0xB8 and len(args) == 1:
        return {"summary": f"Message table {args[0]}", "messageTable": args[0]}
    if opcode in {0xBB, 0xC1, 0xC2} and len(args) >= 2:
        index = _u16(args)
        return {"summary": f"String {index}", "stringIndex": index}
    if opcode in {0xC0, 0xC3, 0xC4} and len(args) >= 3:
        index = _u16(args)
        return {
            "summary": f"String {index} · option/flags 0x{args[2]:02X}",
            "stringIndex": index, "optionFlags": args[2],
        }
    if opcode == 0xC7 and len(args) == 2:
        address = _script_address(args[0])
        return {
            "summary": f"Add item from 0x{address:06X} · category {args[1]}",
            "sourceAddress": address, "category": args[1],
        }
    if opcode == 0xC9 and len(args) == 3:
        item = _u16(args)
        return {
            "summary": f"Has {_lookup(items, item, 'Item')} ({item}) → jump +{args[2]}",
            "itemId": item, "itemName": _lookup(items, item, "Item"), "jumpOffset": args[2],
        }
    if opcode in {0xCA, 0xCB} and len(args) == 2:
        operation = "add" if opcode == 0xCA else "remove"
        verb = "Add" if opcode == 0xCA else "Remove"
        return {
            "summary": f"{verb} item index {args[0]} · category {args[1]}",
            "itemIndex": args[0], "category": args[1], "operation": operation,
        }
    if opcode == 0xCC and len(args) == 3:
        gold = _u16(args)
        return {"summary": f"Has {gold} G → jump +{args[2]}", "gold": gold, "jumpOffset": args[2]}
    if opcode == 0xCD and len(args) == 2:
        gold = _u16(args)
        return {"summary": f"Add {gold} G", "gold": gold, "operation": "add"}
    if opcode == 0xCE and len(args) == 2:
        gold = _u16(args)
        return {"summary": f"Remove {gold} G", "gold": gold, "operation": "remove"}
    if opcode in {0x80, 0x81} and len(args) == 1:
        pc = args[0]
        return {"summary": f"{_lookup(players, pc, 'PC')} ({pc})", "playerId": pc}
    if opcode in {0xCF, 0xD2} and len(args) == 2:
        pc = args[0]
        return {
            "summary": f"{_lookup(players, pc, 'PC')} ({pc}) → jump +{args[1]}",
            "playerId": pc, "jumpOffset": args[1],
        }
    if opcode in {0xD0, 0xD1, 0xD3, 0xD4, 0xD6} and len(args) == 1:
        pc = args[0]
        return {"summary": f"{_lookup(players, pc, 'PC')} ({pc})", "playerId": pc}
    if opcode == 0xD5 and len(args) == 3:
        pc = args[0]
        return {
            "summary": f"Equip {_lookup(players, pc, 'PC')} ({pc}) · item index {args[1]} · category {args[2]}",
            "playerId": pc, "itemIndex": args[1], "category": args[2],
        }
    if opcode == 0xD7 and len(args) == 3:
        address = _script_address(args[2])
        return {
            "summary": f"Item index {args[0]} · category {args[1]} quantity → 0x{address:06X}",
            "itemIndex": args[0], "category": args[1], "storeAddress": address,
        }
    if opcode == 0xD8 and len(args) == 2:
        enabled = [name for byte_index, bit, name in BATTLE_FLAGS if args[byte_index] & bit]
        return {
            "summary": "Battle" + (" · " + ", ".join(enabled) if enabled else " · default flags"),
            "flags1": args[0], "flags2": args[1], "enabledFlags": enabled,
        }
    if 0xDC <= opcode <= 0xE1 and len(args) == 5:
        scene = _u16(args)
        facing, x, y = args[2], args[3], args[4]
        return {
            "summary": f"{_lookup(scenes, scene, 'Scene')} ({scene}) · facing {facing} · ({x}, {y})",
            "sceneId": scene, "sceneName": _lookup(scenes, scene, "Scene"),
            "facing": facing, "tileX": x, "tileY": y,
        }
    if opcode == 0xE3 and len(args) == 1 and args[0] in {0, 1}:
        return {"summary": f"Explore mode {'on' if args[0] else 'off'}", "enabled": bool(args[0])}
    if opcode == 0xE8 and len(args) == 1:
        return {"summary": f"Sound effect {args[0]}", "soundId": args[0]}
    if opcode == 0xEA and len(args) == 1:
        return {"summary": f"Music {args[0]}", "musicId": args[0]}
    if opcode == 0xF0 and len(args) == 1:
        return {"summary": f"Darken screen · duration {args[0]} (raw)", "duration": args[0]}
    return None


def decorate_event(payload: dict, labels: dict) -> dict:
    for obj in payload.get("objects", []):
        for function in obj.get("functions", []):
            for command in function.get("commands", []):
                semantic = command_semantics(command, labels)
                if semantic:
                    command["semantic"] = semantic
    payload["labelLanguages"] = labels.get("languages", {})
    return payload
