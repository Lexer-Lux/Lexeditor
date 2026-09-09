"""Safe semantic annotations for read-only Steam field-event disassembly.

Only argument meanings directly established by the PC command definitions are
annotated here. The raw command bytes remain authoritative and command writing
is deliberately out of scope.
"""

from __future__ import annotations


def _u16(data: bytes, offset: int = 0) -> int:
    return int.from_bytes(data[offset:offset + 2], "little")


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

    if opcode == 0x83 and len(args) == 3:
        enemy = _u16(args)
        return {"summary": f"Enemy {enemy} · slot/flags 0x{args[2]:02X}", "enemyId": enemy, "slotFlags": args[2]}
    if opcode == 0xB8 and len(args) == 1:
        return {"summary": f"Message table {args[0]}", "messageTable": args[0]}
    if opcode in {0xBB, 0xC1, 0xC2} and len(args) >= 2:
        index = _u16(args)
        return {"summary": f"String {index}", "stringIndex": index}
    if opcode in {0xC0, 0xC3, 0xC4} and len(args) >= 3:
        index = _u16(args)
        return {"summary": f"String {index} · option/flags 0x{args[2]:02X}", "stringIndex": index, "optionFlags": args[2]}
    if opcode == 0xC9 and len(args) == 3:
        item = _u16(args)
        return {"summary": f"Has {_lookup(items, item, 'Item')} ({item}) → jump +{args[2]}", "itemId": item, "jumpOffset": args[2]}
    if opcode in {0x80, 0x81} and len(args) == 1:
        pc = args[0]
        return {"summary": f"{_lookup(players, pc, 'PC')} ({pc})", "playerId": pc}
    if opcode in {0xCF, 0xD2} and len(args) == 2:
        pc = args[0]
        return {"summary": f"{_lookup(players, pc, 'PC')} ({pc}) → jump +{args[1]}", "playerId": pc, "jumpOffset": args[1]}
    if opcode in {0xD0, 0xD1, 0xD3, 0xD4, 0xD6} and len(args) == 1:
        pc = args[0]
        return {"summary": f"{_lookup(players, pc, 'PC')} ({pc})", "playerId": pc}
    if 0xDC <= opcode <= 0xE1 and len(args) == 5:
        scene = _u16(args)
        facing, x, y = args[2], args[3], args[4]
        return {
            "summary": f"{_lookup(scenes, scene, 'Scene')} ({scene}) · facing {facing} · ({x}, {y})",
            "sceneId": scene, "sceneName": _lookup(scenes, scene, "Scene"),
            "facing": facing, "tileX": x, "tileY": y,
        }
    if opcode == 0xE8 and len(args) == 1:
        return {"summary": f"Sound effect {args[0]}", "soundId": args[0]}
    if opcode == 0xEA and len(args) == 1:
        return {"summary": f"Music {args[0]}", "musicId": args[0]}
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
