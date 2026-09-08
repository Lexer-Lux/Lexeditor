"""Read-only installed-data research for the FF7R Dog Whistle tweak.

This probe answers the questions that determine whether the item can be authored
mostly in cooked data or needs structural/runtime injection:
- does Item.uasset already contain a whistle/dog FName we can use without adding
  a new name-map entry or hijacking an existing consumable row?
- does Chapter.AddKeyItem_Array reference ordinary Item row tags on this build?
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
                  index: dict, language: str) -> tuple[dict[str, str], list[str]]:
    lookup: dict[str, str] = {}
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
    return lookup, errors


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


def _resolved_entry_text(entry, text: dict[str, str]) -> list[dict]:
    rows = []
    for prop, value in entry.values.items():
        for candidate in _walk_strings(value):
            resolved = text.get(candidate)
            if resolved:
                rows.append({"property": prop, "textId": candidate, "text": resolved})
    return rows


def probe_dog_whistle_sources(game_root: Path, data_root: Path, project_root: Path,
                              index: dict, *, language: str = "US") -> dict:
    text, errors = _all_text_map(game_root, data_root, project_root, index, language)
    item = _load_data(game_root, data_root, index, ITEM_TABLE)
    chapter = _load_data(game_root, data_root, index, CHAPTER_TABLE)
    battle_chara = _load_data(game_root, data_root, index, BATTLE_CHARA_TABLE)
    enemy_book = _load_data(game_root, data_root, index, ENEMY_BOOK_TABLE)

    item_result = {
        "asset": item.asset if item else "",
        "whistleNameMapCandidates": [],
        "rowCandidates": [],
        "itemProperties": [prop.name for prop in item.properties] if item else [],
    }
    item_tags: set[str] = set()
    if item:
        item_tags = {entry.tag for entry in item.entries}
        item_result["whistleNameMapCandidates"] = sorted({
            name for name in item.uasset.names if _contains_term(name, WHISTLE_TERMS)
        })[:MAX_ROWS]
        for entry in item.entries:
            evidence = [entry.tag, *_walk_strings(entry.values)]
            resolved = _resolved_entry_text(entry, text)
            if (any(_contains_term(value, WHISTLE_TERMS) for value in evidence)
                    or any(_contains_term(row["text"], WHISTLE_TERMS) for row in resolved)):
                item_result["rowCandidates"].append({
                    "tag": entry.tag,
                    "values": entry.values,
                    "resolvedText": resolved,
                })
                if len(item_result["rowCandidates"]) >= MAX_ROWS:
                    break

    chapter_result = {
        "asset": chapter.asset if chapter else "",
        "addKeyItemPropertyPresent": False,
        "chaptersWithKeyItemAdds": [],
        "referencedKeyItemsThatAreItemRows": [],
    }
    if chapter:
        props = {prop.name for prop in chapter.properties}
        chapter_result["addKeyItemPropertyPresent"] = "AddKeyItem_Array" in props
        referenced: set[str] = set()
        for entry in chapter.entries:
            values = entry.values.get("AddKeyItem_Array", [])
            if not isinstance(values, list) or not values:
                continue
            referenced.update(str(value) for value in values if value)
            resolved = _resolved_entry_text(entry, text)
            chapter_result["chaptersWithKeyItemAdds"].append({
                "tag": entry.tag,
                "uniqueId": entry.values.get("UniqueID"),
                "chapterNameId": entry.values.get("ChapterNameID"),
                "chapterName": text.get(str(entry.values.get("ChapterNameID", "")), ""),
                "addKeyItems": list(values),
                "resolvedText": resolved,
            })
            if len(chapter_result["chaptersWithKeyItemAdds"]) >= MAX_ROWS:
                break
        chapter_result["referencedKeyItemsThatAreItemRows"] = sorted(referenced & item_tags)

    enemy_rows: dict[str, dict] = {}
    if enemy_book:
        for entry in enemy_book.entries:
            resolved = _resolved_entry_text(entry, text)
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
            "A whistle-like FName already present in Item.uasset would avoid adding a new DataObject name-map entry; it is not automatically safe to use as an item row ID.",
            "The Chapter/AddKeyItem correlation reports whether this installed build's key-item IDs are also ordinary Item table row tags.",
            "No existing consumable row should be repurposed merely to avoid structural item authoring.",
            "Canine matches are research candidates and require installed battle verification, especially Darkstar/boss/scripted cases.",
        ],
    }
