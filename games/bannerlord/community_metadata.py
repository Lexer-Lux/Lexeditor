"""Read extended Bannerlord dependency metadata from SubModule.xml.

This module normalizes the community metadata used by BLSE/BUTR plus the
legacy/optional dependency tags that Bannerlord.ModuleManager folds into the
same dependency model.  It is deliberately read-only: unknown XML attributes
and structures remain untouched by Lexeditor until a structured writer has an
explicit schema for them.
"""
from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET


_VALID_ORDERS = {"LoadBeforeThis", "LoadAfterThis"}
_VERSION_TYPES = {"a": 0, "b": 1, "e": 2, "v": 3, "d": 4}
_MAX_COMPONENT = 2**31 - 1
_MIN_COMPONENT = -(2**31)


def _truth(value: str | None) -> bool:
    return str(value or "").strip().casefold() == "true"


def _application_version(value: str, *, as_min: bool) -> tuple[int, int, int, int, int] | None:
    """Mirror BUTR ModuleManager's ApplicationVersion.TryParse ordering values."""
    raw = str(value or "").strip()
    parts = raw.split(".")
    if len(parts) not in {3, 4} or not parts[0]:
        return None
    version_type = _VERSION_TYPES.get(parts[0][0])
    if version_type is None:
        return None

    default = 0 if as_min else _MAX_COMPONENT
    values = [default, default, default, default]
    components = [parts[0][1:], parts[1], parts[2]] + ([parts[3]] if len(parts) == 4 else [])
    wildcard = False
    for index, component in enumerate(components):
        if wildcard:
            break
        try:
            values[index] = int(component)
        except ValueError:
            if component != "*":
                return None
            if index == 0:
                # ModuleManager uses int.MinValue for every component for a
                # major wildcard regardless of min/max parsing mode.
                values = [_MIN_COMPONENT] * 4
            else:
                values[index:] = [default] * (4 - index)
            wildcard = True
    return version_type, *values


def community_version_matches(required: str, installed: str) -> bool | None:
    """Apply BUTR community-version minimum/range semantics.

    A single community ``version`` is a minimum, including wildcard forms such
    as ``v2.1.*``. A ``min-max`` expression is an inclusive range. ``None``
    means either side could not be parsed and Lexeditor should avoid claiming a
    match or mismatch.
    """
    requirement = str(required or "").strip()
    if not requirement:
        return None
    installed_version = _application_version(installed, as_min=True)
    if installed_version is None:
        return None

    if "-" in requirement:
        low_raw, high_raw = requirement.replace(" ", "").split("-", 1)
        low = _application_version(low_raw, as_min=True)
        high = _application_version(high_raw, as_min=False)
        if low is None or high is None:
            return None
        return low <= installed_version <= high

    minimum = _application_version(requirement, as_min=True)
    if minimum is None:
        return None
    return minimum <= installed_version


def _row(
    element: ET.Element,
    *,
    index: int,
    origin: str,
    id_attribute: str,
    order: str = "",
    optional: bool = False,
    incompatible: bool = False,
    version: str = "",
) -> dict | None:
    module_id = str(element.attrib.get(id_attribute) or "").strip()
    if not module_id:
        return None
    return {
        "index": index,
        "id": module_id,
        "order": order if order in _VALID_ORDERS else "",
        "optional": optional,
        "incompatible": incompatible,
        "version": version,
        "origin": origin,
        "attributes": dict(element.attrib),
    }


def read_community_dependencies(path: Path) -> list[dict]:
    """Return ModuleManager-normalized extended dependency rows in precedence order.

    ``ModuleInfoExtended.FromXml`` appends rows in this order before native
    ``DependedModule`` rows are considered: BLSE ``DependedModuleMetadatas``,
    ``LoadAfterModules``, then launcher optional-dependency tags.  Matching that
    order matters because ModuleManager de-duplicates dependencies by ID with
    the first row winning.
    """
    root = ET.parse(Path(path)).getroot()
    rows: list[dict] = []

    parent = root.find("DependedModuleMetadatas")
    if parent is not None:
        for index, element in enumerate(
            child for child in list(parent) if child.tag == "DependedModuleMetadata"
        ):
            order = str(element.attrib.get("order") or "").strip()
            row = _row(
                element,
                index=index,
                origin="DependedModuleMetadatas",
                id_attribute="id",
                order=order,
                optional=_truth(element.attrib.get("optional")),
                incompatible=_truth(element.attrib.get("incompatible")),
                version=str(element.attrib.get("version") or "").strip(),
            )
            if row is not None:
                rows.append(row)

    load_after = root.find("LoadAfterModules")
    if load_after is not None:
        for index, element in enumerate(
            child for child in list(load_after) if child.tag == "LoadAfterModule"
        ):
            row = _row(
                element,
                index=index,
                origin="LoadAfterModules",
                id_attribute="Id",
                order="LoadAfterThis",
            )
            if row is not None:
                rows.append(row)

    optional_elements: list[tuple[str, ET.Element]] = []
    depended_modules = root.find("DependedModules")
    if depended_modules is not None:
        optional_elements.extend(
            ("DependedModules/OptionalDependModule", child)
            for child in list(depended_modules)
            if child.tag == "OptionalDependModule"
        )
    optional_root = root.find("OptionalDependModules")
    if optional_root is not None:
        optional_elements.extend(
            (f"OptionalDependModules/{child.tag}", child)
            for child in list(optional_root)
            if child.tag in {"OptionalDependModule", "DependModule"}
        )
    for index, (origin, element) in enumerate(optional_elements):
        row = _row(
            element,
            index=index,
            origin=origin,
            id_attribute="Id",
            optional=True,
        )
        if row is not None:
            rows.append(row)

    return rows
