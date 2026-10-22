"""Attach GF spellbook project data to the existing FF8 GF/settings APIs."""
from __future__ import annotations

from pathlib import Path
from core.numeric_values import integer_value

from . import formats, gameplay_settings, gf_spellbooks, paths


FIELD = "__spellbook"
_installed = False


def _root_for_dataset(dataset: str) -> Path | None:
    if dataset == "current":
        return paths.PROJECT_ROOT
    if dataset == "vanilla":
        return None
    if dataset.startswith("mod:"):
        return formats._managed_root(dataset)
    if dataset.startswith("reference:"):
        reference_id = dataset.partition(":")[2]
        reference = next((row for row in formats.reference_roots() if row["id"] == reference_id), None)
        return Path(reference["path"]) if reference else None
    return None


def install() -> None:
    global _installed
    if _installed:
        return
    _installed = True

    original_kernel_rows = formats.kernel_rows
    original_save_kernel = formats.save_kernel
    original_initialize = gameplay_settings.initialize_project

    def kernel_rows(section_id: int, dataset: str = "current") -> dict:
        result = original_kernel_rows(section_id, dataset)
        if section_id != 3:
            return result
        root = _root_for_dataset(dataset)
        document = gf_spellbooks.load(root) if root is not None else {"schemaVersion": 1, "books": []}
        books = {book["gfId"]: book for book in document["books"]}
        for row in result.get("rows", []):
            row["spellbook"] = books.get(int(row["id"]))
        settings = gameplay_settings.load()
        result["spellbook"] = {
            "enabled": settings.get("gfSpellbooksEnabled", False),
            "runtimeActive": bool(settings.get("gfSpellbooksEnabled")) and bool(settings.get("singleGf")) and not bool(settings.get("sharedMagicInventory")),
            "magicIds": sorted(gf_spellbooks.MAGIC_IDS),
            "abilityIds": sorted(gf_spellbooks.ABILITY_IDS),
            "magicOptions": [
                {"id": int(row["id"]), "name": row["name"]}
                for row in formats.MAGIC if int(row["id"]) in gf_spellbooks.MAGIC_IDS
            ],
            "abilityOptions": [
                {"id": int(row["id"]), "name": row["name"]}
                for row in formats.INIT_ABILITIES if int(row["id"]) in gf_spellbooks.ABILITY_IDS
            ],
            "maxPages": 8,
            "slotsPerPage": 4,
            "runtimeOwnedBy": "FFNx DLL",
            "runtimeRequires": {"singleGf": True, "sharedMagicInventory": False},
        }
        return result

    def save_kernel(section_id: int, edits: list[dict]) -> dict:
        section_id = integer_value(section_id, "Kernel section id")
        if not isinstance(edits, list):
            raise gf_spellbooks.SpellbookError("Kernel edits must be an array")
        for edit in edits:
            if not isinstance(edit, dict) or set(edit) != {"id", "field", "value"}:
                raise gf_spellbooks.SpellbookError("Kernel edit requires id, field and value")
            if not isinstance(edit["field"], str):
                raise gf_spellbooks.SpellbookError("Kernel field must be text")
        if section_id != 3:
            return original_save_kernel(section_id, edits)
        binary_edits, spellbook_edits = [], []
        seen = set()
        for edit in edits:
            if edit.get("field") != FIELD:
                binary_edits.append(edit)
                continue
            gf = integer_value(edit["id"], "GF spellbook id", gf_spellbooks.SpellbookError)
            if not 0 <= gf < 16 or gf in seen:
                raise gf_spellbooks.SpellbookError("Invalid or duplicate GF spellbook edit")
            seen.add(gf)
            pages = edit.get("value")
            if pages is not None and not isinstance(pages, list):
                raise gf_spellbooks.SpellbookError("GF spellbook pages must be a list or null")
            spellbook_edits.append((gf, pages))

        if not spellbook_edits:
            return original_save_kernel(section_id, binary_edits) if binary_edits else {
                "saved": 0, "file": "", "files": []
            }
        current = gf_spellbooks.load(paths.PROJECT_ROOT)
        by_gf = {book["gfId"]: book for book in current["books"]}
        for gf, pages in spellbook_edits:
            if pages is None:
                by_gf.pop(gf, None)
            else:
                by_gf[gf] = {"gfId": gf, "pages": pages}
        document = gf_spellbooks.validate({
            "schemaVersion": gf_spellbooks.SCHEMA_VERSION,
            "books": [by_gf[key] for key in sorted(by_gf)],
        })
        settings = gameplay_settings.load()
        active = (bool(settings.get("gfSpellbooksEnabled")) and bool(settings.get("singleGf"))
                  and not bool(settings.get("sharedMagicInventory")))
        runtime = gf_spellbooks.runtime_bytes(document if active else {"schemaVersion": 1, "books": []})
        result = original_save_kernel(section_id, binary_edits) if binary_edits else {
            "saved": 0, "file": "", "files": []
        }
        gf_spellbooks.save(paths.PROJECT_ROOT, document)
        gf_spellbooks._atomic(paths.PROJECT_ROOT / gf_spellbooks.RUNTIME_RELATIVE, runtime)
        result = dict(result)
        result["saved"] = int(result.get("saved", 0)) + len(spellbook_edits)
        files = list(result.get("files", []))
        for target in (paths.PROJECT_ROOT / gf_spellbooks.FILE_NAME,
                       paths.PROJECT_ROOT / gf_spellbooks.RUNTIME_RELATIVE):
            if str(target) not in files:
                files.append(str(target))
        result["files"] = files
        if not result.get("file"):
            result["file"] = files[0]
        return result

    def initialize_project(project_root) -> None:
        original_initialize(project_root)
        document = {"schemaVersion": gf_spellbooks.SCHEMA_VERSION, "books": []}
        gf_spellbooks.save(project_root, document)

    formats.kernel_rows = kernel_rows
    formats.save_kernel = save_kernel
    gameplay_settings.initialize_project = initialize_project
