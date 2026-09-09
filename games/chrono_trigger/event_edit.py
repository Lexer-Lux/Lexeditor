"""Structurally safe field-event argument edits for Chrono Trigger Steam.

This deliberately does not provide a script assembler. It may replace argument
bytes of an already-decoded fixed-width command, which cannot move any function
pointer or change the size of the Atel resource. Commands whose argument bytes
also encode their own length/mode remain read-only.
"""

from __future__ import annotations

from .data import OverlayStore, sha256
from .events import event_entries, get_event, parse_event


VARIABLE_OR_UNRESOLVED = frozenset({0x2E, 0x4E, 0x88, 0x9E, 0x9F, 0xF1, 0xFF})


def _event_path(store: OverlayStore, event_id: int) -> str:
    matches = {number: path for number, path in event_entries(store)}
    event_id = int(event_id)
    if event_id not in matches:
        raise ValueError(f"Unknown Chrono Trigger field event: {event_id}")
    return matches[event_id]


def _argument_bytes(value: str | bytes | bytearray, expected: int) -> bytes:
    if isinstance(value, str):
        try:
            data = bytes.fromhex(value)
        except ValueError as error:
            raise ValueError("Event arguments must be hexadecimal bytes") from error
    else:
        data = bytes(value)
    if len(data) != expected:
        raise ValueError(f"This command requires exactly {expected} argument byte(s), got {len(data)}")
    return data


def save_event_arguments(store: OverlayStore, event_id: int, object_id: int, function_id: int,
                         command_index: int, expected_sha256: str,
                         arguments: str | bytes | bytearray) -> dict:
    """Replace argument bytes for one existing fixed-width command."""
    path = _event_path(store, event_id)
    raw, _origin = store.read(path, "mine")
    if sha256(raw) != str(expected_sha256):
        raise RuntimeError("The field event changed since it was opened; reload before saving")
    parsed = parse_event(raw)
    object_id, function_id, command_index = int(object_id), int(function_id), int(command_index)
    if not 0 <= object_id < len(parsed["objects"]):
        raise ValueError(f"Event object is outside the script: {object_id}")
    functions = parsed["objects"][object_id]["functions"]
    if not 0 <= function_id < len(functions):
        raise ValueError(f"Event function is outside object {object_id}: {function_id}")
    commands = functions[function_id]["commands"]
    if not 0 <= command_index < len(commands):
        raise ValueError(f"Event command is outside function {object_id}:{function_id}: {command_index}")
    command = commands[command_index]
    opcode = int(command["opcode"])
    if opcode in VARIABLE_OR_UNRESOLVED:
        raise ValueError(
            f"Opcode 0x{opcode:02X} has variable or unresolved PC width and remains read-only"
        )
    expected_length = int(command["argumentBytes"])
    replacement = _argument_bytes(arguments, expected_length)
    if expected_length == 0:
        raise ValueError("This command has no argument bytes to edit")

    # parse_event command offsets are relative to raw[1:], because byte zero is
    # the Atel object count. The opcode itself remains untouched.
    absolute = 1 + int(command["offset"]) + 1
    output = bytearray(raw)
    if absolute + expected_length > len(output):
        raise ValueError("Decoded event argument span is outside the resource")
    output[absolute:absolute + expected_length] = replacement
    if len(output) != len(raw):
        raise AssertionError("Fixed-width event edit unexpectedly changed resource size")
    store.write(path, bytes(output))
    result = get_event(store, int(event_id), "mine")
    result["savedCommand"] = {
        "objectId": object_id,
        "functionId": function_id,
        "commandIndex": command_index,
        "opcode": opcode,
        "argumentsHex": replacement.hex(" ").upper(),
    }
    return result
