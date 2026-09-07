"""Attach GF spellbook project data to the existing FF8 GF/settings APIs."""
from __future__ import annotations

from pathlib import Path

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


def _sync_runtime(project: Path, *, enabled: bool) -> Path:
    target = Path(project) / gf_spellbooks.RUNTIME_RELATIVE
    document = gf_spellbooks.load(project) if enabled else {"schemaVersion": 1, "books": []}
    gf_spellbooks._atomic(target, gf_spellbooks.runtime_bytes(document))
    return target


def install() -> None:
    global _installed
    if _installed:
        return
    _installed = True

    original_kernel_rows = formats.kernel_rows
    original_save_kernel = formats.save_kernel
    original_settings_save = gameplay_settings.save
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
        result["spellbook"] = {
            "magicIds": sorted(gf_spellbooks.MAGIC_IDS),
            "abilityIds": sorted(gf_spellbooks.ABILITY_IDS),
            "maxPages": 8,
            "slotsPerPage": 4,
            "runtimeOwnedBy": "FFNx DLL",
        }
        return result

    def save_kernel(section_id: int, edits: list[dict]) -> dict:
        if section_id != 3:
            return original_save_kernel(section_id, edits)
        binary_edits, spellbook_edits = [], []
        seen = set()
        for edit in edits:
            if edit.get("field") != FIELD:
                binary_edits.append(edit)
                continue
            gf = int(edit.get("id", -1))
            if not 0 <= gf < 16 or gf in seen:
                raise gf_spellbooks.SpellbookError("Invalid or duplicate GF spellbook edit")
            seen.add(gf)
            pages = edit.get("value")
            if pages is not None and not isinstance(pages, list):
                raise gf_spellbooks.SpellbookError("GF spellbook pages must be a list or null")
            spellbook_edits.append((gf, pages))

        result = original_save_kernel(section_id, binary_edits) if binary_edits else {
            "saved": 0, "file": "", "files": []
        }
        if not spellbook_edits:
            return result
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
        gf_spellbooks.save(paths.PROJECT_ROOT, document)
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

    def settings_save(data: dict, game_root=None, project_root=None, *,
                      install_runtime=False, runtime_root=None) -> dict:
        result = original_settings_save(
            data, game_root, project_root,
            install_runtime=install_runtime, runtime_root=runtime_root,
        )
        project = (project_root or paths.PROJECT_ROOT).resolve()
        active = bool(data.get("singleGf", False)) and not bool(data.get("sharedMagicInventory", False))
        _sync_runtime(project, enabled=active)
        return result

    def initialize_project(project_root) -> None:
        original_initialize(project_root)
        document = {"schemaVersion": gf_spellbooks.SCHEMA_VERSION, "books": []}
        gf_spellbooks.save(project_root, document)

    formats.kernel_rows = kernel_rows
    formats.save_kernel = save_kernel
    gameplay_settings.save = settings_save
    gameplay_settings.initialize_project = initialize_project
