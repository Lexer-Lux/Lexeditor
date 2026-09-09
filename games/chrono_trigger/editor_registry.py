"""Unified named fixed-width field-editor registry for Chrono Trigger Steam."""

from __future__ import annotations

from .bit_ops import apply_bit_op, bit_field_specs, bit_values, decorate_bit_semantics
from .call_ops import apply_call_op, call_field_specs, call_values, decorate_call_semantics
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
from .jump_ops import apply_jump, decorate_jump_semantics, jump_field_specs, jump_values
from .memory_ops import (
    apply_memory_op,
    decorate_memory_semantics,
    memory_field_specs,
    memory_values,
)
from .movement_ops import (
    apply_movement_op,
    decorate_movement_semantics,
    movement_field_specs,
    movement_values,
)
from .object_ops import (
    apply_object_op,
    decorate_object_semantics,
    object_field_specs,
    object_values,
)


def _schema_from_specs(command: dict, specs: list[dict] | None, values: dict | None) -> dict | None:
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


def comparison_editor_schema(command: dict) -> dict | None:
    return _schema_from_specs(command, comparison_field_specs(command), comparison_values(command))


def memory_editor_schema(command: dict) -> dict | None:
    return _schema_from_specs(command, memory_field_specs(command), memory_values(command))


def bit_editor_schema(command: dict) -> dict | None:
    return _schema_from_specs(command, bit_field_specs(command), bit_values(command))


def movement_editor_schema(command: dict) -> dict | None:
    return _schema_from_specs(command, movement_field_specs(command), movement_values(command))


def call_editor_schema(command: dict) -> dict | None:
    return _schema_from_specs(command, call_field_specs(command), call_values(command))


def object_editor_schema(command: dict) -> dict | None:
    return _schema_from_specs(command, object_field_specs(command), object_values(command))


def jump_editor_schema(command: dict) -> dict | None:
    return _schema_from_specs(command, jump_field_specs(command), jump_values(command))


_REGISTRY_BUILDERS = (
    comparison_editor_schema,
    memory_editor_schema,
    bit_editor_schema,
    movement_editor_schema,
    call_editor_schema,
    object_editor_schema,
    jump_editor_schema,
)
_REGISTRY_APPLIERS = (
    apply_comparison,
    apply_memory_op,
    apply_bit_op,
    apply_movement_op,
    apply_call_op,
    apply_object_op,
    apply_jump,
)


def editor_schema(command: dict) -> dict | None:
    for builder in _REGISTRY_BUILDERS:
        schema = builder(command)
        if schema is not None:
            return schema
    return base_editor_schema(command)


def decorate_event_editors(payload: dict) -> dict:
    decorate_comparison_semantics(payload)
    decorate_memory_semantics(payload)
    decorate_bit_semantics(payload)
    decorate_movement_semantics(payload)
    decorate_call_semantics(payload)
    decorate_object_semantics(payload)
    decorate_jump_semantics(payload)
    decorate_base_editors(payload)
    for obj in payload.get("objects", []):
        for function in obj.get("functions", []):
            for command in function.get("commands", []):
                for builder in _REGISTRY_BUILDERS:
                    schema = builder(command)
                    if schema is not None:
                        command["editor"] = schema
                        break
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
    for apply in _REGISTRY_APPLIERS:
        replacement = apply(command, values)
        if replacement is not None:
            return save_event_arguments(
                store, event_id, object_id, function_id, command_index,
                expected_sha256, replacement,
            )
    return save_base_event_fields(
        store, event_id, object_id, function_id, command_index,
        expected_sha256, values,
    )
