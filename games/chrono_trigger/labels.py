"""Localization-backed labels for structured Chrono Trigger Steam data."""

from __future__ import annotations

import re


_LANGUAGE_PREFERENCE = ("en", "us", "eng", "jp", "ja", "fr", "de", "it", "es", "pt", "kr", "ko", "cn", "zh", "tw")
_LOCALIZED_RE = re.compile(r"^Localize/([^/]+)/msg/([^/]+)$", re.IGNORECASE)


def _available(store, filename: str) -> dict[str, str]:
    wanted = filename.casefold()
    found = {}
    for entry in store.archive.entries:
        match = _LOCALIZED_RE.match(entry.path)
        if match and match.group(2).casefold() == wanted:
            found.setdefault(match.group(1).casefold(), entry.path)
    return found


def choose_language(store, filename: str, preferred: str | None = None) -> tuple[str | None, str | None]:
    found = _available(store, filename)
    if not found:
        return None, None
    if preferred and preferred.casefold() in found:
        key = preferred.casefold()
        return key, found[key]
    for key in _LANGUAGE_PREFERENCE:
        if key in found:
            return key, found[key]
    key = sorted(found)[0]
    return key, found[key]


def _lines(store, filename: str, source: str, preferred: str | None = None) -> tuple[list[str], str | None, str | None]:
    language, path = choose_language(store, filename, preferred)
    if path is None:
        return [], None, None
    raw, _origin = store.read(path, source)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return [], language, path
    return text.splitlines(), language, path


def _value(line: str) -> str:
    return line.split(",", 1)[1] if "," in line else line


def label_bundle(store, source: str = "mine", preferred_language: str | None = None) -> dict:
    debug, debug_lang, debug_path = _lines(store, "debug_map.txt", source, preferred_language)
    world, world_lang, world_path = _lines(store, "w_map.txt", source, preferred_language)
    items, item_lang, item_path = _lines(store, "item.txt", source, preferred_language)
    players, player_lang, player_path = _lines(store, "player.txt", source, preferred_language)

    # CTViewer prepends an empty location entry before debug_map rows.
    scene_names = [""] + [_value(line) for line in debug]
    world_source_names = [_value(line) for line in world[106:112]]
    world_order = (0, 1, 2, 3, 4, 4, 4, 5)
    world_names = [
        world_source_names[index] if index < len(world_source_names) else f"World {world_id}"
        for world_id, index in enumerate(world_order)
    ]
    return {
        "kind": "localized-labels",
        "preferredLanguage": preferred_language,
        "languages": {
            "scenes": debug_lang, "worlds": world_lang,
            "items": item_lang, "players": player_lang,
        },
        "paths": {
            "scenes": debug_path, "worlds": world_path,
            "items": item_path, "players": player_path,
        },
        "sceneNames": scene_names,
        "worldNames": world_names,
        "worldExitNames": [_value(line) for line in world[:106]],
        "itemNames": [_value(line) for line in items],
        "playerNames": [_value(line) for line in players[:8]],
    }


def _lookup(values: list[str], index: int, fallback: str) -> str:
    index = int(index)
    if 0 <= index < len(values) and values[index].strip():
        return values[index]
    return fallback


def decorate_scenes(payload: dict, labels: dict) -> dict:
    for row in payload.get("rows", []):
        row["name"] = _lookup(labels["sceneNames"], row["id"], row.get("name") or f"Scene {row['id']:04d}")
    payload["labelLanguage"] = labels["languages"]["scenes"]
    return payload


def decorate_scene_exits(payload: dict, labels: dict) -> dict:
    for row in payload.get("rows", []):
        destination = int(row["values"]["destination"])
        row["derived"]["destinationName"] = _lookup(
            labels["sceneNames"], destination, f"Scene {destination}"
        )
    payload["labelLanguage"] = labels["languages"]["scenes"]
    return payload


def decorate_treasure(payload: dict, labels: dict) -> dict:
    for row in payload.get("rows", []):
        item_id = row.get("derived", {}).get("itemId")
        if item_id is not None:
            row["derived"]["itemName"] = _lookup(labels["itemNames"], item_id, f"Item {item_id}")
        target = row.get("derived", {}).get("targetScene")
        if target is not None:
            row["derived"]["targetSceneName"] = _lookup(labels["sceneNames"], target, f"Scene {target}")
    payload["labelLanguage"] = labels["languages"]["items"] or labels["languages"]["scenes"]
    return payload


def decorate_worlds(payload: dict, labels: dict) -> dict:
    for row in payload.get("rows", []):
        row["name"] = _lookup(labels["worldNames"], row["id"], row.get("name") or f"World {row['id']}")
    payload["labelLanguage"] = labels["languages"]["worlds"]
    return payload


def decorate_world_table(payload: dict, labels: dict) -> dict:
    for row in payload.get("exits", []):
        name_index = int(row["values"]["nameIndex"])
        row["derived"]["exitName"] = _lookup(labels["worldExitNames"], name_index, f"Exit {name_index}")
        scene = int(row["values"]["sceneIndex"])
        if scene != 0x1FF:
            row["derived"]["destinationName"] = _lookup(labels["sceneNames"], scene, f"Scene {scene}")
    payload["labelLanguage"] = labels["languages"]["worlds"] or labels["languages"]["scenes"]
    return payload
