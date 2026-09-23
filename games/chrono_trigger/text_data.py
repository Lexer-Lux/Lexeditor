"""Steam localization text records."""
from __future__ import annotations

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


def load_messages(store: OverlayStore, path: str, source: str = "mine") -> dict:
    path = validate_resource_path(path)
    if not path.startswith("Localize/") or "/msg/" not in path or not path.endswith(".txt"):
        raise ValueError("Only Steam Localize/<lang>/msg/*.txt files use the text editor")
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
    payload, _ = store.read(path, "mine")
    if digest(payload) != expected_sha256:
        raise RuntimeError(f"{path} changed since it was opened; reload before saving")
    text, bom = _decode(payload)
    lines = text.splitlines(keepends=True)
    seen: set[int] = set()
    for edit in edits:
        line_number = int(edit["line"])
        key = str(edit["key"])
        value = str(edit["text"])
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
