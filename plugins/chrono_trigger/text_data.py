"""Steam localization text records."""
from __future__ import annotations
from core.numeric_values import integer_value

from .project import OverlayStore, digest, validate_resource_path


def languages(store: OverlayStore) -> list[str]:
    found = set()
    for path in store.archive.paths("Localize/"):
        parts = path.split("/")
        if len(parts) >= 4 and parts[2] == "msg" and path.endswith(".txt"):
            found.add(parts[1])
    return sorted(found)


def text_files(store: OverlayStore, language: str) -> list[str]:
    if language not in languages(store):
        raise ValueError(f"Unknown Steam language {language}")
    prefix = f"Localize/{language}/msg/"
    return sorted(path for path in store.archive.paths(prefix) if path.endswith(".txt"))


def _decode(payload: bytes) -> tuple[str, bool]:
    bom = payload.startswith(b"\xef\xbb\xbf")
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("This localization file is not UTF-8 and is not editable") from error
    return text, bom


def _message_path(path: str) -> str:
    if not isinstance(path, str):
        raise ValueError("Localization path must be text")
    path = validate_resource_path(path)
    if not path.startswith("Localize/") or "/msg/" not in path or not path.endswith(".txt"):
        raise ValueError("Only Steam Localize/<lang>/msg/*.txt files use the text editor")
    return path


def load_messages(store: OverlayStore, path: str, source: str = "mine") -> dict:
    path = _message_path(path)
    payload, origin = store.read(path, source)
    text, _ = _decode(payload)
    rows = []
    for line_number, raw in enumerate(text.splitlines(keepends=True)):
        body = raw.rstrip("\r\n")
        key, sep, value = body.partition(",")
        if not sep or not key:
            continue
        rows.append({
            "token": f"{line_number}:{key}",
            "key": key,
            "text": value,
            "line": line_number,
        })
    return {"path": path, "source": origin, "sha256": digest(payload), "rows": rows}


def save_messages(store: OverlayStore, path: str, expected_sha256: str, edits: list[dict]) -> dict:
    path = _message_path(path)
    payload, _ = store.read(path, "mine")
    if digest(payload) != expected_sha256:
        raise RuntimeError(f"{path} changed since it was opened; reload before saving")
    text, bom = _decode(payload)
    lines = text.splitlines(keepends=True)
    seen: set[int] = set()
    for edit in edits:
        if not isinstance(edit, dict):
            raise ValueError("Localization edit must be an object")
        line_number = integer_value(edit["line"], "Localization line ID")
        key, value = edit.get("key"), edit.get("text")
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("Localization key and text must be strings")
        if line_number in seen:
            raise ValueError("Duplicate text edit")
        seen.add(line_number)
        if not 0 <= line_number < len(lines):
            raise ValueError("Text edit points outside the file")
        if "\r" in value or "\n" in value:
            raise ValueError("A text record cannot contain a literal line break")
        raw = lines[line_number]
        newline = "\r\n" if raw.endswith("\r\n") else ("\n" if raw.endswith("\n") else ("\r" if raw.endswith("\r") else ""))
        body = raw[:-len(newline)] if newline else raw
        current_key, sep, _ = body.partition(",")
        if not sep or current_key != key:
            raise RuntimeError("Text record identity changed; reload before saving")
        lines[line_number] = f"{key},{value}{newline}"
    encoded = "".join(lines).encode("utf-8")
    if bom:
        encoded = b"\xef\xbb\xbf" + encoded
    store.write(path, expected_sha256, encoded)
    return load_messages(store, path, "mine")
