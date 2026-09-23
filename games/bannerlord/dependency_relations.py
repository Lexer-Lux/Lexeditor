"""Normalize Bannerlord dependency relations with ModuleManager precedence.

The game and community ecosystem expose the same logical relation through
several XML sections.  Bannerlord.ModuleManager evaluates load relations in a
specific order and applies ``DistinctBy(Id)`` with the first row winning.  Keep
that rule in one place so Play and deployment diagnostics cannot drift.
"""
from __future__ import annotations


def _module_id(row: dict) -> str:
    return str(row.get("id") or "").strip()


def _extended_source(row: dict) -> str:
    return "community" if row.get("origin") == "DependedModuleMetadatas" else "extended"


def _mark_precedence(rows: list[dict]) -> list[dict]:
    """Return copies of rows marked with first-ID-wins effectiveness.

    ModuleManager's ``DistinctBy(x => x.Id)`` uses the raw module ID.  Do not
    case-fold here: installed-module lookup is deliberately more forgiving, but
    metadata precedence should mirror the ecosystem implementation.
    """
    first_origin: dict[str, str] = {}
    result = []
    for row in rows:
        module_id = _module_id(row)
        if not module_id:
            continue
        item = dict(row)
        item["id"] = module_id
        if module_id in first_origin:
            item["effective"] = False
            item["shadowedByOrigin"] = first_origin[module_id]
        else:
            item["effective"] = True
            item["shadowedByOrigin"] = ""
            first_origin[module_id] = str(item.get("origin") or item.get("source") or "metadata")
        result.append(item)
    return result


def load_relation_rows(module: dict, extended_rows: list[dict]) -> list[dict]:
    """Return all load-relation candidates in ModuleManager precedence order.

    Order is community/extended non-incompatible metadata, native
    ``DependedModule`` rows, then native ``ModulesToLoadAfterThis`` rows.
    Shadowed rows remain in the result for diagnostics but have
    ``effective=False``.
    """
    candidates: list[dict] = []

    for row in extended_rows:
        if row.get("incompatible"):
            continue
        candidates.append(
            {
                **row,
                "id": _module_id(row),
                "source": _extended_source(row),
                "origin": row.get("origin") or "DependedModuleMetadatas",
                "order": str(row.get("order") or ""),
                "optional": bool(row.get("optional")),
                "incompatible": False,
                "version": str(row.get("version") or "").strip(),
            }
        )

    for row in module.get("dependencies", []):
        candidates.append(
            {
                "id": _module_id(row),
                "source": "native",
                "origin": "DependedModules",
                "order": "LoadBeforeThis",
                "optional": bool(row.get("optional")),
                "incompatible": False,
                "version": str(row.get("dependentVersion") or "").strip(),
                "attributes": dict(row.get("attributes") or {}),
            }
        )

    # ModuleInfoExtended parses this native section as optional. It orders an
    # already-enabled target but does not enable that target on its own.
    for row in module.get("modulesToLoadAfterThis", []):
        candidates.append(
            {
                "id": _module_id(row),
                "source": "native",
                "origin": "ModulesToLoadAfterThis",
                "order": "LoadAfterThis",
                "optional": True,
                "incompatible": False,
                "version": "",
                "attributes": dict(row.get("attributes") or {}),
            }
        )

    return _mark_precedence(candidates)


def effective_load_relations(module: dict, extended_rows: list[dict]) -> list[dict]:
    return [row for row in load_relation_rows(module, extended_rows) if row["effective"]]


def incompatible_relation_rows(module: dict, extended_rows: list[dict]) -> list[dict]:
    """Return incompatibility candidates with their separate first-ID-wins rule."""
    candidates: list[dict] = []
    for row in extended_rows:
        if not row.get("incompatible"):
            continue
        candidates.append(
            {
                **row,
                "id": _module_id(row),
                "source": _extended_source(row),
                "origin": row.get("origin") or "DependedModuleMetadatas",
                "order": str(row.get("order") or ""),
                "optional": bool(row.get("optional")),
                "incompatible": True,
                "version": str(row.get("version") or "").strip(),
            }
        )

    for row in module.get("incompatibleModules", []):
        candidates.append(
            {
                "id": _module_id(row),
                "source": "native",
                "origin": "IncompatibleModules",
                "order": "",
                "optional": True,
                "incompatible": True,
                "version": "",
                "attributes": dict(row.get("attributes") or {}),
            }
        )
    return _mark_precedence(candidates)


def dependency_declaration_conflicts(module: dict, extended_rows: list[dict]) -> list[str]:
    """Return ModuleManager-style contradictions in one module's declarations.

    These checks intentionally inspect direction-specific/raw declaration sets,
    not only the first-ID-wins effective load set. ModuleManager validates these
    contradictions separately from sorting.
    """
    issues: list[str] = []

    load_ids = {row["id"] for row in effective_load_relations(module, extended_rows)}
    incompatible_ids = {
        row["id"] for row in effective_incompatible_relations(module, extended_rows)
    }
    for module_id in sorted(load_ids & incompatible_ids, key=str.casefold):
        issues.append(f"{module_id} is declared both loadable and incompatible")

    before_ids = {
        _module_id(row)
        for row in extended_rows
        if row.get("order") == "LoadBeforeThis" and _module_id(row)
    }
    before_ids.update(
        _module_id(row)
        for row in module.get("dependencies", [])
        if _module_id(row)
    )
    after_ids = {
        _module_id(row)
        for row in extended_rows
        if row.get("order") == "LoadAfterThis" and _module_id(row)
    }
    after_ids.update(
        _module_id(row)
        for row in module.get("modulesToLoadAfterThis", [])
        if _module_id(row)
    )
    for module_id in sorted(before_ids & after_ids, key=str.casefold):
        issues.append(f"{module_id} is declared both LoadBeforeThis and LoadAfterThis")

    for row in extended_rows:
        module_id = _module_id(row)
        order = str(row.get("order") or "")
        if module_id and row.get("incompatible") and order in {"LoadBeforeThis", "LoadAfterThis"}:
            issues.append(f"{module_id} is marked incompatible but also declares {order}")

    return list(dict.fromkeys(issues))


def effective_incompatible_relations(module: dict, extended_rows: list[dict]) -> list[dict]:
    return [row for row in incompatible_relation_rows(module, extended_rows) if row["effective"]]
