"""Read-only installed-data research for the FF7R Dog Whistle tweak.

This probe answers the questions that determine whether the item can be authored
mostly in cooked data or needs structural/runtime injection:
- does Item.uasset already contain an unused whistle/dog FName that could name a
  genuinely new row without expanding the package name map?
- which existing Item rows expose an AbilityID and can serve only as structural
  references for battle-usable item shape (never as IDs to repurpose)?
- which Chapter row(s) have evidence for Chapter 4 and expose AddKeyItem_Array?
- which BattleCharaSpec/EnemyBook rows correspond to canine enemies?
- which native APIs/signatures are promising for awarding/using the item and
  redirecting enemy AI via AEndBattleAIController::SetTarget?
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

from .archive import extract_pair
from .dataobject import DataObjectPackage
from .native_probe import probe_installed_exe
from .text_storage import load_text_package


ITEM_TABLE = "item"
CHAPTER_TABLE = "chapter"
BATTLE_CHARA_TABLE = "battlecharaspec"
ENEMY_BOOK_TABLE = "enemybook"

WHISTLE_TERMS = ("whistle", "dogwhistle", "dog_whistle")
CANINE_TERMS = (
    "guard dog", "wrath hound", "wrathhound", "bloodhound", "darkstar",
    "wayward wolf", "hound", "canine", "dog",
)
NATIVE_NEEDLES = (
    "SetTarget",
    "GetBattleAI",
    "GetBattleAIControllerFromID",
    "GetBattleCharaSpec_DataTableID",
    "Item_Add",
    "AddKeyItem",
    "Whistle",
    "Dog",
    "Hound",
)
MAX_ROWS = 256


def _basename(asset: str) -> str:
    return PurePosixPath(asset).name.casefold()


def _find_row(index: dict, basename: str) -> dict | None:
    for row in index.get("assets", []):
        if row.get("synthetic"):
            continue
        if _basename(str(row.get("asset", ""))) == basename:
            return row
    return None


def _load_data(game_root: Path, data_root: Path, index: dict, basename: str):
    row = _find_row(index, basename)
    if row is None:
        return None
    uasset, uexp = extract_pair(game_root, data_root, index, row["asset"])
    return DataObjectPackage(uasset, uexp, asset=row["asset"])


def _walk_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for child in value:
            yield from _walk_strings(child)
    elif isinstance(value, dict):
        for child in value.values():
            yield from _walk_strings(child)


def _all_text_map(game_root: Path, data_root: Path, project_root: Path,
                  index: dict, language: str) -> tuple[dict[str, str], dict[str, str], list[str]]:
    lookup: dict[str, str] = {}
    owners: dict[str, str] = {}
    errors: list[str] = []
    language = language.upper()
    for row in index.get("textAssets", []):
        if str(row.get("language", "")).upper() != language:
            continue
        asset = str(row.get("asset", ""))
        try:
            package, _a, _b, _using = load_text_package(
                game_root, data_root, project_root, index, asset, vanilla=True)
        except Exception as error:
            errors.append(f"{asset}: {error}")
            continue
        for entry in package.entries:
            if entry.id:
                lookup[entry.id] = entry.text
                owners[entry.id] = asset
    return lookup, owners, errors


def _contains_term(value: str, terms: tuple[str, ...]) -> bool:
    folded = value.casefold().replace("_", " ")
    compact = "".join(ch for ch in value.casefold() if ch.isalnum())
    for term in terms:
        normalized = term.casefold().replace("_", " ")
        if normalized in folded:
            return True
        if "".join(ch for ch in normalized if ch.isalnum()) in compact:
            return True
    return False


def _resolved_entry_text(entry, text: dict[str, str], owners: dict[str, str]) -> list[dict]:
    rows = []
    for prop, value in entry.values.items():
        for candidate in _walk_strings(value):
            resolved = text.get(candidate)
            if resolved:
                rows.append({
                    "property": prop,
                    "textId": candidate,
                    "text": resolved,
                    "textAsset": owners.get(candidate, ""),
                })
    return rows


def _chapter4_signals(entry, resolved: list[dict]) -> list[str]:
    """Return evidence signals only; never declare Chapter 4 from row order."""
    signals: list[str] = []
    tag_compact = "".join(ch for ch in entry.tag.casefold() if ch.isalnum())
    if any(token in tag_compact for token in ("chapter04", "chapter4", "chap04", "chap4", "ch04")):
        signals.append("row-tag")
    unique = str(entry.values.get("UniqueID", "")).strip().casefold()
    unique_compact = "".join(ch for ch in unique if ch.isalnum())
    if unique_compact in {"4", "04", "chapter4", "chapter04", "chap4", "chap04", "ch04"}:
        signals.append("unique-id")
    for row in resolved:
        value = " ".join(str(row.get("text", "")).casefold().replace("-", " ").split())
        compact = "".join(ch for ch in value if ch.isalnum())
        if "chapter 4" in value or "chapter04" in compact or "chapter4" in compact:
            signals.append(f"resolved-text:{row.get('property', 'unknown')}")
    return sorted(set(signals))


def probe_dog_whistle_sources(game_root: Path, data_root: Path, project_root: Path,
                              index: dict, *, language: str = "US") -> dict:
    text, text_owners, errors = _all_text_map(
        game_root, data_root, project_root, index, language)
    item = _load_data(game_root, data_root, index, ITEM_TABLE)
    chapter = _load_data(game_root, data_root, index, CHAPTER_TABLE)
    battle_chara = _load_data(game_root, data_root, index, BATTLE_CHARA_TABLE)
    enemy_book = _load_data(game_root, data_root, index, ENEMY_BOOK_TABLE)

    item_result = {
        "asset": item.asset if item else "",
        "whistleNameMapCandidates": [],
        "unusedWhistleNameMapCandidates": [],
        "rowCandidates": [],
        "abilityBackedTemplateCandidates": [],
        "itemProperties": [prop.name for prop in item.properties] if item else [],
    }
    item_tags: set[str] = set()
    if item:
        item_tags = {entry.tag for entry in item.entries}
        whistle_names = sorted({
            name for name in item.uasset.names if _contains_term(name, WHISTLE_TERMS)
        })[:MAX_ROWS]
        item_result["whistleNameMapCandidates"] = whistle_names
        item_result["unusedWhistleNameMapCandidates"] = [
            name for name in whistle_names if name not in item_tags
        ]
        for entry in item.entries:
            evidence = [entry.tag, *_walk_strings(entry.values)]
            resolved = _resolved_entry_text(entry, text, text_owners)
            if (any(_contains_term(value, WHISTLE_TERMS) for value in evidence)
                    or any(_contains_term(row["text"], WHISTLE_TERMS) for row in resolved)):
                item_result["rowCandidates"].append({
                    "tag": entry.tag,
                    "values": entry.values,
                    "resolvedText": resolved,
                })
            ability_id = entry.values.get("AbilityID")
            if ability_id not in (None, "", "None", "NONE"):
                item_result["abilityBackedTemplateCandidates"].append({
                    "tag": entry.tag,
                    "abilityId": ability_id,
                    "resolvedText": resolved,
                })
            if (len(item_result["rowCandidates"]) >= MAX_ROWS
                    and len(item_result["abilityBackedTemplateCandidates"]) >= MAX_ROWS):
                break
        item_result["rowCandidates"] = item_result["rowCandidates"][:MAX_ROWS]
        item_result["abilityBackedTemplateCandidates"] = item_result["abilityBackedTemplateCandidates"][:MAX_ROWS]

    chapter_result = {
        "asset": chapter.asset if chapter else "",
        "addKeyItemPropertyPresent": False,
        "chaptersWithKeyItemAdds": [],
        "chapter4Candidates": [],
        "referencedKeyItemsThatAreItemRows": [],
    }
    if chapter:
        props = {prop.name for prop in chapter.properties}
        chapter_result["addKeyItemPropertyPresent"] = "AddKeyItem_Array" in props
        referenced: set[str] = set()
        for entry in chapter.entries:
            values = entry.values.get("AddKeyItem_Array", [])
            resolved = _resolved_entry_text(entry, text, text_owners)
            signals = _chapter4_signals(entry, resolved)
            row = {
                "tag": entry.tag,
                "uniqueId": entry.values.get("UniqueID"),
                "chapterNameId": entry.values.get("ChapterNameID"),
                "chapterName": text.get(str(entry.values.get("ChapterNameID", "")), ""),
                "addKeyItems": list(values) if isinstance(values, list) else [],
                "resolvedText": resolved,
                "chapter4Signals": signals,
            }
            if signals:
                chapter_result["chapter4Candidates"].append(row)
            if not isinstance(values, list) or not values:
                continue
            referenced.update(str(value) for value in values if value)
            chapter_result["chaptersWithKeyItemAdds"].append(row)
            if len(chapter_result["chaptersWithKeyItemAdds"]) >= MAX_ROWS:
                break
        chapter_result["chapter4Candidates"] = chapter_result["chapter4Candidates"][:MAX_ROWS]
        chapter_result["referencedKeyItemsThatAreItemRows"] = sorted(referenced & item_tags)

    enemy_rows: dict[str, dict] = {}
    if enemy_book:
        for entry in enemy_book.entries:
            resolved = _resolved_entry_text(entry, text, text_owners)
            if (_contains_term(entry.tag, CANINE_TERMS)
                    or any(_contains_term(value, CANINE_TERMS) for value in _walk_strings(entry.values))
                    or any(_contains_term(row["text"], CANINE_TERMS) for row in resolved)):
                enemy_rows[entry.tag] = {
                    "enemyBookId": entry.tag,
                    "resolvedText": resolved,
                    "values": entry.values,
                    "battleCharaRows": [],
                }
    if battle_chara:
        for entry in battle_chara.entries:
            enemy_id = str(entry.values.get("EnemyBookID", ""))
            if enemy_id in enemy_rows:
                enemy_rows[enemy_id]["battleCharaRows"].append(entry.tag)
            elif _contains_term(entry.tag, CANINE_TERMS):
                enemy_rows.setdefault(enemy_id or entry.tag, {
                    "enemyBookId": enemy_id,
                    "resolvedText": [],
                    "values": {},
                    "battleCharaRows": [],
                })["battleCharaRows"].append(entry.tag)

    native = probe_installed_exe(game_root, needles=NATIVE_NEEDLES)
    return {
        "language": language.upper(),
        "item": item_result,
        "chapterProgression": chapter_result,
        "canineEnemies": list(enemy_rows.values())[:MAX_ROWS],
        "native": native,
        "scanErrors": errors,
        "knownContracts": {
            "itemUseField": "Item.AbilityID",
            "chapterAwardField": "Chapter.AddKeyItem_Array",
            "enemyRetargetMethod": "AEndBattleAIController::SetTarget(AEndCharacter*)",
        },
        "notes": [
            "An UNUSED whistle-like FName already present in Item.uasset can name a genuinely new cloned row without expanding the DataObject name map; an existing row with that tag is never treated as safe to repurpose.",
            "AbilityID-backed Item rows are structural template candidates only. Their ID/effect is never reused for Dog Whistle without proving the exact battle-use contract and overriding/suppressing the template behavior.",
            "Text evidence records the exact installed text resource that owns each resolved ID so a future new name/description can be placed in the corresponding localized resource rather than guessed globally.",
            "Chapter 4 candidates require tag/UniqueID/resolved-name evidence; row order is never used as a Chapter 4 identifier.",
            "The Chapter/AddKeyItem correlation reports whether this installed build's key-item IDs are also ordinary Item table row tags.",
            "Canine matches are research candidates and require installed battle verification, especially Darkstar/boss/scripted cases.",
        ],
    }