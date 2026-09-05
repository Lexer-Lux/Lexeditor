"""Validated GF spellbook data and stock-independent view/selection core.

This is not a runtime patch. Native menu integration must preserve reservation
and queue semantics, status restrictions, and the shared-stock transaction.
Page and slot order are array order; no implicit sorting or stock filtering.
"""
from __future__ import annotations
from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
from typing import Mapping

SCHEMA_VERSION = 1
FILE_NAME = "gf-spellbooks.json"
# FFNx save_data.h: G_FORCE_NUM=16, complete_abilities[16]. The kernel's
# current named stock spells are1..56; unknown/summon IDs are not spell choices.
_magic_schema = json.loads((Path(__file__).parent / "schema" / "magic.json").read_text(encoding="utf-8"))
MAGIC_IDS = frozenset(row["id"] for row in _magic_schema["magic"] if 0 < row["id"] < 64 and not row["name"].startswith("Unknown"))
ABILITY_IDS = frozenset(range(1, 116))


class SpellbookError(ValueError):
    pass


def _integer(value, label, allowed=None):
    if type(value) is not int or (allowed is not None and value not in allowed):
        raise SpellbookError(f"Invalid {label}")
    return value


def validate(document):
    """Return a detached canonical document, rejecting all ambiguous entries."""
    if not isinstance(document, dict) or set(document) != {"schemaVersion", "books"}:
        raise SpellbookError("Spellbooks require schemaVersion and books")
    if type(document["schemaVersion"]) is not int or document["schemaVersion"] != SCHEMA_VERSION:
        raise SpellbookError("Unsupported spellbook schema")
    if not isinstance(document["books"], list):
        raise SpellbookError("Books must be a list")
    books, seen_gfs = [], set()
    for book in document["books"]:
        if not isinstance(book, dict) or set(book) != {"gfId", "pages"}:
            raise SpellbookError("A book requires gfId and pages")
        gf = _integer(book["gfId"], "GF", range(16))
        if gf in seen_gfs:
            raise SpellbookError("A GF can have only one spellbook")
        seen_gfs.add(gf)
        if not isinstance(book["pages"], list):
            raise SpellbookError("Pages must be a list")
        pages, seen_magic = [], set()
        for page in book["pages"]:
            if not isinstance(page, list):
                raise SpellbookError("Each page must be a list of spell slots")
            slots = []
            for slot in page:
                if not isinstance(slot, dict) or set(slot) != {"magicId", "abilityId"}:
                    raise SpellbookError("A slot requires magicId and optional abilityId (null)")
                magic = _integer(slot["magicId"], "spell", MAGIC_IDS)
                ability = slot["abilityId"]
                if ability is not None:
                    _integer(ability, "ability", ABILITY_IDS)
                if magic in seen_magic:
                    raise SpellbookError("A spell can occur only once in a GF spellbook")
                seen_magic.add(magic)
                slots.append({"magicId": magic, "abilityId": ability})
            pages.append(slots)
        books.append({"gfId": gf, "pages": pages})
    return {"schemaVersion": SCHEMA_VERSION, "books": books}


def load(project: Path):
    target = Path(project) / FILE_NAME
    if not target.exists():
        return {"schemaVersion": SCHEMA_VERSION, "books": []}
    try:
        return validate(json.loads(target.read_text(encoding="utf-8")))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SpellbookError(f"Cannot read {FILE_NAME}: {error}") from error


def save(project: Path, document):
    """Atomically persist only project data; never writes runtime/save data."""
    checked = validate(document)
    directory = Path(project)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / FILE_NAME
    descriptor, temporary = tempfile.mkstemp(prefix=".gf-spellbooks-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write((json.dumps(checked, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return checked


def _stock(stock):
    result = dict(stock)
    for magic, amount in result.items():
        _integer(magic, "stock spell", MAGIC_IDS)
        _integer(amount, "stock amount", range(256))
    return result


@dataclass(frozen=True)
class SlotView:
    magic_id: int
    ability_id: int | None
    page: int
    index: int
    amount: int
    usable: bool
    reason: str | None


def project_view(document, gf_id, stock: Mapping[int, int], learned_abilities,
                 native_usable: Mapping[int, bool], reserved: Mapping[int, int] | None = None):
    """Return explicit pages for one GF. Missing native eligibility fails closed.

    gf_id=None means no resolved GF, not GF0. Page/index are zero-based.
    Stock amount stays visible even when an ability or native status blocks it.
    The caller supplies abilities learned by THIS GF, not another junctioned GF.
    """
    checked = validate(document)
    quantities = _stock(stock)
    learned = set(learned_abilities)
    for ability in learned:
        _integer(ability, "learned ability", ABILITY_IDS)
    held = _stock(reserved or {})
    for magic, usable in native_usable.items():
        _integer(magic, "native spell", MAGIC_IDS)
        if type(usable) is not bool:
            raise SpellbookError("Native eligibility must be boolean")
    if gf_id is None:
        return []
    _integer(gf_id, "GF", range(16))
    book = next((book for book in checked["books"] if book["gfId"] == gf_id), None)
    if book is None:
        return []
    pages = []
    for page_index, page in enumerate(book["pages"]):
        entries = []
        for slot_index, slot in enumerate(page):
            magic, ability = slot["magicId"], slot["abilityId"]
            amount = quantities.get(magic, 0)
            reason = ("ability" if ability is not None and ability not in learned else
                      "stock" if amount == 0 else
                      "reserved" if amount <= held.get(magic, 0) else
                      "native" if native_usable.get(magic) is not True else None)
            entries.append(SlotView(magic, ability, page_index, slot_index, amount, reason is None, reason))
        pages.append(entries)
    return pages


def debit_selection(document, gf_id, page, index, expected_magic_id, stock,
                    learned_abilities, native_usable, *, amount=1, reserved=None):
    """Revalidate a selection and return new stock by ID; never mutate inputs.

    This represents the commit operation. Passing the expected spell ID also
    rejects stale menu indexes after a book edit. Native queue integration must
    release this command's own reservation before committing its debit.
    """
    _integer(page, "page")
    _integer(index, "slot")
    _integer(amount, "cast amount", range(1, 256))
    _integer(expected_magic_id, "selected spell", MAGIC_IDS)
    pages = project_view(document, gf_id, stock, learned_abilities, native_usable, reserved)
    if page < 0 or page >= len(pages) or index < 0 or index >= len(pages[page]):
        raise SpellbookError("The selected spellbook slot no longer exists")
    slot = pages[page][index]
    if slot.magic_id != expected_magic_id:
        raise SpellbookError("The selected spellbook slot changed")
    if not slot.usable or slot.amount - (reserved or {}).get(slot.magic_id, 0) < amount:
        raise SpellbookError("The selected spell is not usable")
    result = _stock(stock)
    result[slot.magic_id] -= amount
    return result
