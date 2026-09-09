"""Named editors for proven fixed-width Chrono Trigger Steam field commands.

The schemas here sit on top of :mod:`event_edit`: they only rewrite argument
bytes of an existing command and never change opcode, command size, function
pointers or object counts. Unspecified bit flags and bytes are preserved.
"""

from __future__ import annotations

from dataclasses import dataclass

from .data import OverlayStore
from .event_edit import save_event_arguments
from .events import get_event


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    minimum: int = 0
    maximum: int = 255
    kind: str = "integer"

    def descriptor(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "kind": self.kind,
            "min": self.minimum,
            "max": self.maximum,
        }


U8 = 0xFF
U16 = 0xFFFF
SCRIPT_MEM_START = 0x7F0200
SCRIPT_MEM_LAST = SCRIPT_MEM_START + U8 * 2

BATTLE_BITS = {
    "noWinPose": (0, 0x01, "No win pose"),
    "bottomMenu": (0, 0x02, "Bottom battle menu"),
    "smallPcSolidity": (0, 0x04, "Small PC solidity"),
    "unused08": (0, 0x08, "Unknown flag 0x08"),
    "staticEnemies": (0, 0x10, "Static enemies"),
    "specialEvent": (0, 0x20, "Special event"),
    "unknown40": (0, 0x40, "Unknown flag 0x40"),
    "noRun": (0, 0x80, "Cannot run"),
    "unknown201": (1, 0x01, "Unknown flag 2:0x01"),
    "unknown202": (1, 0x02, "Unknown flag 2:0x02"),
    "unknown204": (1, 0x04, "Unknown flag 2:0x04"),
    "unknown208": (1, 0x08, "Unknown flag 2:0x08"),
    "unknown210": (1, 0x10, "Unknown flag 2:0x10"),
    "noGameOver": (1, 0x20, "No game over"),
    "mapMusic": (1, 0x40, "Keep map music"),
    "regroup": (1, 0x80, "Regroup party"),
}


def _u16(data: bytes, offset: int = 0) -> int:
    return int.from_bytes(data[offset:offset + 2], "little")


def _put_u16(data: bytearray, offset: int, value: int) -> None:
    data[offset:offset + 2] = int(value).to_bytes(2, "little")


def _int(value, minimum: int, maximum: int, label: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be an integer") from error
    if not minimum <= number <= maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return number


def _bool(value, label: str) -> bool:
    if isinstance(value, bool):
        return value
    if value in (0, 1):
        return bool(value)
    raise ValueError(f"{label} must be true or false")


def _script_address(offset: int) -> int:
    return SCRIPT_MEM_START + int(offset) * 2


def _script_offset(value, label: str) -> int:
    address = _int(value, SCRIPT_MEM_START, SCRIPT_MEM_LAST, label)
    if (address - SCRIPT_MEM_START) % 2:
        raise ValueError(f"{label} must be an even script-memory address")
    return (address - SCRIPT_MEM_START) // 2


def _command(store: OverlayStore, event_id: int, object_id: int,
             function_id: int, command_index: int) -> tuple[dict, dict]:
    event = get_event(store, int(event_id), "mine")
    object_id, function_id, command_index = int(object_id), int(function_id), int(command_index)
    try:
        function = event["objects"][object_id]["functions"][function_id]
        command = function["commands"][command_index]
    except (IndexError, KeyError) as error:
        raise ValueError(
            f"Unknown event command {event_id}:{object_id}:{function_id}:{command_index}"
        ) from error
    return event, command


def _base_args(command: dict) -> bytearray:
    try:
        return bytearray.fromhex(command.get("argumentsHex", ""))
    except ValueError as error:
        raise ValueError("Decoded command arguments are not valid hexadecimal bytes") from error


def editor_schema(command: dict) -> dict | None:
    """Return named fixed-width controls for one decoded command, if supported."""
    opcode = int(command["opcode"])
    fields: list[Field] = []
    editor = "fixed-fields"
    if opcode == 0x83:
        fields = [Field("enemyId", "Enemy ID", 0, U16), Field("slot", "Enemy slot", 0, 0x7F),
                  Field("static", "Static enemy", 0, 1, "boolean")]
    elif 0xDC <= opcode <= 0xE1:
        fields = [Field("sceneId", "Destination scene", 0, U16), Field("facing", "Facing", 0, 3),
                  Field("tileX", "Destination X", 0, U8), Field("tileY", "Destination Y", 0, U8)]
    elif opcode in {0xBB, 0xC1, 0xC2}:
        fields = [Field("stringIndex", "String index", 0, U16)]
    elif opcode in {0xC0, 0xC3, 0xC4}:
        fields = [Field("stringIndex", "String index", 0, U16),
                  Field("optionFlags", "Option/line flags", 0, U8)]
    elif opcode == 0xC7:
        fields = [Field("sourceAddress", "Item ID address", SCRIPT_MEM_START, SCRIPT_MEM_LAST),
                  Field("category", "Item category (raw)", 0, U8)]
    elif opcode == 0xC9:
        fields = [Field("itemId", "Item ID", 0, U16), Field("jumpOffset", "Jump bytes", 0, U8)]
    elif opcode in {0xCA, 0xCB}:
        fields = [Field("itemIndex", "Item index (within category)", 0, U8),
                  Field("category", "Item category (raw)", 0, U8)]
    elif opcode == 0xCC:
        fields = [Field("gold", "Gold", 0, U16), Field("jumpOffset", "Jump bytes", 0, U8)]
    elif opcode in {0xCD, 0xCE}:
        fields = [Field("gold", "Gold", 0, U16)]
    elif opcode == 0xD5:
        fields = [Field("playerId", "Player character", 0, U8),
                  Field("itemIndex", "Item index (within category)", 0, U8),
                  Field("category", "Item category (raw)", 0, U8)]
    elif opcode == 0xD7:
        fields = [Field("itemIndex", "Item index (within category)", 0, U8),
                  Field("category", "Item category (raw)", 0, U8),
                  Field("storeAddress", "Store quantity at", SCRIPT_MEM_START, SCRIPT_MEM_LAST)]
    elif opcode in {0x80, 0x81, 0xD0, 0xD1, 0xD3, 0xD4, 0xD6}:
        fields = [Field("playerId", "Player character", 0, U8)]
    elif opcode in {0xCF, 0xD2}:
        fields = [Field("playerId", "Player character", 0, U8),
                  Field("jumpOffset", "Jump bytes", 0, U8)]
    elif opcode in {0xE8, 0xEA}:
        fields = [Field("id", "Sound ID" if opcode == 0xE8 else "Music ID", 0, U8)]
    elif opcode == 0xD8:
        editor = "battle-flags"
        fields = [Field(key, label, 0, 1, "boolean") for key, (_byte, _bit, label) in BATTLE_BITS.items()]
    else:
        return None
    return {
        "editor": editor,
        "opcode": opcode,
        "opcodeHex": f"0x{opcode:02X}",
        "fixedWidth": True,
        "fields": [field.descriptor() for field in fields],
        "values": editor_values(command),
    }


def editor_values(command: dict) -> dict:
    opcode = int(command["opcode"])
    args = _base_args(command)
    if opcode == 0x83 and len(args) == 3:
        return {"enemyId": _u16(args), "slot": args[2] & 0x7F, "static": bool(args[2] & 0x80)}
    if 0xDC <= opcode <= 0xE1 and len(args) == 5:
        return {"sceneId": _u16(args), "facing": args[2], "tileX": args[3], "tileY": args[4]}
    if opcode in {0xBB, 0xC1, 0xC2} and len(args) == 2:
        return {"stringIndex": _u16(args)}
    if opcode in {0xC0, 0xC3, 0xC4} and len(args) == 3:
        return {"stringIndex": _u16(args), "optionFlags": args[2]}
    if opcode == 0xC7 and len(args) == 2:
        return {"sourceAddress": _script_address(args[0]), "category": args[1]}
    if opcode == 0xC9 and len(args) == 3:
        return {"itemId": _u16(args), "jumpOffset": args[2]}
    if opcode in {0xCA, 0xCB} and len(args) == 2:
        return {"itemIndex": args[0], "category": args[1]}
    if opcode == 0xCC and len(args) == 3:
        return {"gold": _u16(args), "jumpOffset": args[2]}
    if opcode in {0xCD, 0xCE} and len(args) == 2:
        return {"gold": _u16(args)}
    if opcode == 0xD5 and len(args) == 3:
        return {"playerId": args[0], "itemIndex": args[1], "category": args[2]}
    if opcode == 0xD7 and len(args) == 3:
        return {"itemIndex": args[0], "category": args[1], "storeAddress": _script_address(args[2])}
    if opcode in {0x80, 0x81, 0xD0, 0xD1, 0xD3, 0xD4, 0xD6} and len(args) == 1:
        return {"playerId": args[0]}
    if opcode in {0xCF, 0xD2} and len(args) == 2:
        return {"playerId": args[0], "jumpOffset": args[1]}
    if opcode in {0xE8, 0xEA} and len(args) == 1:
        return {"id": args[0]}
    if opcode == 0xD8 and len(args) == 2:
        return {key: bool(args[byte_index] & bit) for key, (byte_index, bit, _label) in BATTLE_BITS.items()}
    return {}


def _apply(command: dict, values: dict) -> bytes:
    opcode = int(command["opcode"])
    args = _base_args(command)
    schema = editor_schema(command)
    if schema is None:
        raise ValueError(f"Opcode 0x{opcode:02X} has no named fixed-width editor")
    allowed = {field["key"] for field in schema["fields"]}
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"Unknown fields for opcode 0x{opcode:02X}: {', '.join(sorted(unknown))}")

    if opcode == 0x83:
        if "enemyId" in values:
            _put_u16(args, 0, _int(values["enemyId"], 0, U16, "Enemy ID"))
        slot = _int(values.get("slot", args[2] & 0x7F), 0, 0x7F, "Enemy slot")
        static = _bool(values.get("static", bool(args[2] & 0x80)), "Static enemy")
        args[2] = slot | (0x80 if static else 0)
    elif 0xDC <= opcode <= 0xE1:
        if "sceneId" in values:
            _put_u16(args, 0, _int(values["sceneId"], 0, U16, "Destination scene"))
        mapping = (("facing", 2, 0, 3, "Facing"), ("tileX", 3, 0, U8, "Destination X"),
                   ("tileY", 4, 0, U8, "Destination Y"))
        for key, offset, minimum, maximum, label in mapping:
            if key in values:
                args[offset] = _int(values[key], minimum, maximum, label)
    elif opcode in {0xBB, 0xC1, 0xC2}:
        if "stringIndex" in values:
            _put_u16(args, 0, _int(values["stringIndex"], 0, U16, "String index"))
    elif opcode in {0xC0, 0xC3, 0xC4}:
        if "stringIndex" in values:
            _put_u16(args, 0, _int(values["stringIndex"], 0, U16, "String index"))
        if "optionFlags" in values:
            args[2] = _int(values["optionFlags"], 0, U8, "Option/line flags")
    elif opcode == 0xC7:
        if "sourceAddress" in values:
            args[0] = _script_offset(values["sourceAddress"], "Item ID address")
        if "category" in values:
            args[1] = _int(values["category"], 0, U8, "Item category")
    elif opcode == 0xC9:
        if "itemId" in values:
            _put_u16(args, 0, _int(values["itemId"], 0, U16, "Item ID"))
        if "jumpOffset" in values:
            args[2] = _int(values["jumpOffset"], 0, U8, "Jump bytes")
    elif opcode in {0xCA, 0xCB}:
        if "itemIndex" in values:
            args[0] = _int(values["itemIndex"], 0, U8, "Item index")
        if "category" in values:
            args[1] = _int(values["category"], 0, U8, "Item category")
    elif opcode == 0xCC:
        if "gold" in values:
            _put_u16(args, 0, _int(values["gold"], 0, U16, "Gold"))
        if "jumpOffset" in values:
            args[2] = _int(values["jumpOffset"], 0, U8, "Jump bytes")
    elif opcode in {0xCD, 0xCE}:
        if "gold" in values:
            _put_u16(args, 0, _int(values["gold"], 0, U16, "Gold"))
    elif opcode == 0xD5:
        if "playerId" in values:
            args[0] = _int(values["playerId"], 0, U8, "Player character")
        if "itemIndex" in values:
            args[1] = _int(values["itemIndex"], 0, U8, "Item index")
        if "category" in values:
            args[2] = _int(values["category"], 0, U8, "Item category")
    elif opcode == 0xD7:
        if "itemIndex" in values:
            args[0] = _int(values["itemIndex"], 0, U8, "Item index")
        if "category" in values:
            args[1] = _int(values["category"], 0, U8, "Item category")
        if "storeAddress" in values:
            args[2] = _script_offset(values["storeAddress"], "Store quantity address")
    elif opcode in {0x80, 0x81, 0xD0, 0xD1, 0xD3, 0xD4, 0xD6}:
        if "playerId" in values:
            args[0] = _int(values["playerId"], 0, U8, "Player character")
    elif opcode in {0xCF, 0xD2}:
        if "playerId" in values:
            args[0] = _int(values["playerId"], 0, U8, "Player character")
        if "jumpOffset" in values:
            args[1] = _int(values["jumpOffset"], 0, U8, "Jump bytes")
    elif opcode in {0xE8, 0xEA}:
        if "id" in values:
            args[0] = _int(values["id"], 0, U8, "Sound ID" if opcode == 0xE8 else "Music ID")
    elif opcode == 0xD8:
        for key, value in values.items():
            byte_index, bit, label = BATTLE_BITS[key]
            if _bool(value, label):
                args[byte_index] |= bit
            else:
                args[byte_index] &= ~bit
    return bytes(args)


def save_event_fields(store: OverlayStore, event_id: int, object_id: int, function_id: int,
                      command_index: int, expected_sha256: str, values: dict) -> dict:
    """Patch named fields and delegate the invariant-preserving write."""
    if not isinstance(values, dict):
        raise ValueError("Event field changes must be an object")
    _event, command = _command(store, event_id, object_id, function_id, command_index)
    replacement = _apply(command, values)
    return save_event_arguments(
        store, event_id, object_id, function_id, command_index,
        expected_sha256, replacement,
    )


def decorate_event_editors(payload: dict) -> dict:
    """Attach named editor schemas to supported commands in an event response."""
    for obj in payload.get("objects", []):
        for function in obj.get("functions", []):
            for command in function.get("commands", []):
                schema = editor_schema(command)
                if schema is not None:
                    command["editor"] = schema
    return payload
