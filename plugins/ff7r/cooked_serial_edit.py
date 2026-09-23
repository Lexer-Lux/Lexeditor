"""Fail-closed fixed-width edits for already-proven FF7R cooked property values.

This module deliberately does not discover visual ownership and is not wired to
Better Lock-on. It only provides the narrow mutation primitive needed once an
installed package has independently proved one exact LinearColor property owner.
The property is re-probed before and after mutation and only its 16-byte value
payload may change.
"""

from __future__ import annotations

import math
import struct
from typing import Any, Iterable

from .cooked_serial_probe import extract_serialized_name_refs


MAX_ABS_LINEAR_COLOR = 1_000_000.0


def _rgba_bytes(values: Iterable[float], *, field: str) -> tuple[tuple[float, float, float, float], bytes]:
    rows = tuple(values)
    if len(rows) != 4:
        raise ValueError(f"{field} must contain exactly four RGBA components")
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in rows):
        raise TypeError(f"{field} RGBA components must be numeric")
    normalized = tuple(float(value) for value in rows)
    if any(not math.isfinite(value) or abs(value) > MAX_ABS_LINEAR_COLOR for value in normalized):
        raise ValueError(f"{field} RGBA components must be finite and bounded")
    try:
        payload = struct.pack("<ffff", *normalized)
    except (OverflowError, struct.error) as error:
        raise ValueError(f"{field} RGBA components cannot be represented as float32") from error
    return normalized, payload


def _select_unique_ref(
    report: dict[str, Any],
    *,
    property_name: str,
    class_name: str,
    object_name: str,
) -> dict[str, Any]:
    if not report.get("mappingTrusted"):
        raise ValueError(
            "serialized export mapping is not trusted: "
            + str(report.get("mappingReason") or "unknown reason")
        )
    matches = [
        row for row in report.get("refs", ())
        if row.get("linearColorValuePlausible")
        and str(row.get("name", "")) == property_name
        and str(row.get("className", "")) == class_name
        and str(row.get("objectName", "")) == object_name
    ]
    if len(matches) != 1:
        raise ValueError(
            "expected exactly one proven LinearColor property candidate for "
            f"{class_name}.{object_name}.{property_name}; found {len(matches)}"
        )
    return dict(matches[0])


def _absolute_value_range(ref: dict[str, Any], uexp_size: int) -> tuple[int, int]:
    relative_tag = ref.get("exportRelativeOffset")
    absolute_tag = ref.get("uexpOffset")
    value_start = ref.get("valueOffset")
    value_end = ref.get("valueEndOffset")
    if not all(isinstance(value, int) for value in (relative_tag, absolute_tag, value_start, value_end)):
        raise ValueError("LinearColor candidate is missing integer serialized offsets")
    if value_end - value_start != 16:
        raise ValueError("LinearColor candidate does not own exactly 16 value bytes")
    export_start = absolute_tag - relative_tag
    absolute_start = export_start + value_start
    absolute_end = export_start + value_end
    if absolute_start < 0 or absolute_end < absolute_start or absolute_end > uexp_size:
        raise ValueError("LinearColor value range lies outside the paired .uexp")
    return absolute_start, absolute_end


def rewrite_unique_linear_color(
    uasset: bytes,
    uexp: bytes,
    *,
    property_name: str,
    class_name: str,
    object_name: str,
    expected_rgba: Iterable[float],
    replacement_rgba: Iterable[float],
    label: str = "cooked package",
) -> tuple[bytes, dict[str, Any]]:
    """Replace one exact 16-byte LinearColor payload after strict self-validation.

    The caller must already know the exact class/object/property semantic owner.
    Supplying merely a tint-like name is insufficient: discovery is repeated from
    the bytes, uniqueness is mandatory, and the current 16 bytes must exactly
    equal the caller-provided expected float32 representation.
    """
    property_name = str(property_name).strip()
    class_name = str(class_name).strip()
    object_name = str(object_name).strip()
    if not property_name or not class_name or not object_name:
        raise ValueError("property_name, class_name, and object_name are required")

    expected_values, expected_bytes = _rgba_bytes(expected_rgba, field="expected_rgba")
    replacement_values, replacement_bytes = _rgba_bytes(
        replacement_rgba, field="replacement_rgba"
    )
    before_report = extract_serialized_name_refs(
        uasset,
        uexp,
        tokens=(property_name,),
        label=label,
    )
    before_ref = _select_unique_ref(
        before_report,
        property_name=property_name,
        class_name=class_name,
        object_name=object_name,
    )
    start, end = _absolute_value_range(before_ref, len(uexp))
    if uexp[start:end] != expected_bytes:
        raise ValueError(
            "installed LinearColor bytes do not match expected_rgba; refusing stale or wrong-owner rewrite"
        )

    changed = bytearray(uexp)
    changed[start:end] = replacement_bytes
    changed_bytes = bytes(changed)
    if len(changed_bytes) != len(uexp):
        raise AssertionError("fixed-width LinearColor rewrite changed .uexp length")
    if changed_bytes[:start] != uexp[:start] or changed_bytes[end:] != uexp[end:]:
        raise AssertionError("LinearColor rewrite changed bytes outside the proven value range")

    after_report = extract_serialized_name_refs(
        uasset,
        changed_bytes,
        tokens=(property_name,),
        label=label,
    )
    after_ref = _select_unique_ref(
        after_report,
        property_name=property_name,
        class_name=class_name,
        object_name=object_name,
    )
    after_start, after_end = _absolute_value_range(after_ref, len(changed_bytes))
    if (after_start, after_end) != (start, end):
        raise AssertionError("LinearColor property layout changed after fixed-width rewrite")
    if changed_bytes[after_start:after_end] != replacement_bytes:
        raise AssertionError("LinearColor replacement did not round-trip through the serialized probe")

    return changed_bytes, {
        "property": property_name,
        "className": class_name,
        "objectName": object_name,
        "uexpValueOffset": start,
        "valueSize": 16,
        "expectedRgba": list(expected_values),
        "replacementRgba": list(replacement_values),
        "beforeDecoded": dict(before_ref.get("linearColorValue") or {}),
        "afterDecoded": dict(after_ref.get("linearColorValue") or {}),
        "mappingReason": str(after_report.get("mappingReason", "")),
        "fixedWidth": True,
        "bytesOutsideValuePreserved": True,
        "notes": [
            "This primitive proves only a fixed-width serialized LinearColor rewrite.",
            "It does not prove that the selected property owns the FF7R lock-on reticle or that the widget is visible only while locked.",
            "Better Lock-on must not invoke this primitive until installed ownership/state evidence is independently validated.",
        ],
    }
