"""Unified named fixed-width field-editor registry for Chrono Trigger Steam."""

from __future__ import annotations

from .comparisons import (
    apply_comparison,
    comparison_field_specs,
    comparison_values,
    decorate_comparison_semantics,
)
from .data import OverlayStore
from .event_edit import save_event_arguments
from .events import get_event
from .field_editors import (
    Field,
    decorate_event_editors as decorate_base_editors,
    editor_schema as base_editor_schema,
    save_event_fields as save_base_event_fields,
)


def comparison_editor_schema(command: dict) -> dict | None:
    specs = comparison_field_specs(command)
    values = comparison_values(command)
    if specs is None or values is None:
        return None
    fields = [
        Field(
            spec["key"], spec["label"],
            int(spec.get("minimum", 0)), int(spec.get("maximum", 255)),
            str(spec.get("kind", "integer")),
        )
        for spec in specs
    ]
    opcode = int(command["opcode"])
    return {
        "editor": "fixed-fields",
        "opcode": opcode,
        "opcodeHex": f"0x{opcode:02X}",
        "fixedWidth": True,
        "fields": [field.descriptor() for field in fields],
        "values": values,
    }


def editor_schema(command: dict) -> dict | None:
    comparison = comparison_editor_schema(command)
    if comparison is not None:
        return comparison
    return base_editor_schema(command)


def decorate_event_editors(payload: dict) -> dict:
    decorate_comparison_semantics(payload)
    decorate_base_editors(payload)
    for obj in payload.get("objects", []):
        for function in obj.get("functions", []):
            for command in function.get("commands", []):
                comparison = comparison_editor_schema(command)
                if comparison is not None:
                    command["editor"] = comparison
    return payload


def _command(store: OverlayStore, event_id: int, object_id: int,
             function_id: int, command_index: int) -> dict:
    event = get_event(store, int(event_id), "mine")
    object_id, function_id, command_index = int(object_id), int(function_id), int(command_index)
    try:
        return event["objects"][object_id]["functions"][function_id]["commands"][command_index]
    except (IndexError, KeyError) as error:
        raise ValueError(
            f"Unknown event command {event_id}:{object_id}:{function_id}:{command_index}"
        ) from error


def save_event_fields(store: OverlayStore, event_id: int, object_id: int, function_id: int,
                      command_index: int, expected_sha256: str, values: dict) -> dict:
    if not isinstance(values, dict):
        raise ValueError("Event field changes must be an object")
    command = _command(store, event_id, object_id, function_id, command_index)
    replacement = apply_comparison(command, values)
    if replacement is None:
        return save_base_event_fields(
            store, event_id, object_id, function_id, command_index,
            expected_sha256, values,
        )
    return save_event_arguments(
        store, event_id, object_id, function_id, command_index,
        expected_sha256, replacement,
    )
