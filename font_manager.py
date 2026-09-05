"""Verified, atomic installation for game-specific Lexeditor fonts."""

from __future__ import annotations

import hashlib
import os
import tempfile
import threading
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from plugin_api import GamePlugin, PluginFont


ROOT = Path(__file__).resolve().parent
FONT_LOG = ROOT / "logs" / "font-download.log"
MAX_FONT_BYTES = 8 * 1024 * 1024
_LOG_LOCK = threading.Lock()
_FORMAT_MAGIC = {
    "ttf": (b"\x00\x01\x00\x00", b"true", b"typ1"),
    "otf": (b"OTTO",),
    "woff": (b"wOFF",),
    "woff2": (b"wOF2",),
}
FontFetcher = Callable[[str], bytes]


def _valid_font(path: Path, file_format: str | None = None,
                expected_sha256: str | None = None) -> bool:
    if not path.is_file() or path.stat().st_size < 44:
        return False
    expected = file_format or path.suffix.casefold().lstrip(".")
    signatures = _FORMAT_MAGIC.get(expected)
    if not signatures:
        return False
    with path.open("rb") as stream:
        if stream.read(4) not in signatures:
            return False
        if expected_sha256 is None:
            return True
        stream.seek(0)
        digest = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
        return digest.hexdigest().casefold() == expected_sha256.casefold()


def _installed_path(font: PluginFont) -> Path | None:
    if _valid_font(font.destination, font.file_format, font.sha256):
        return font.destination
    for path in font.alternatives:
        if _valid_font(path):
            return path
    return None


def font_status(plugin: GamePlugin, error: str = "") -> dict:
    items = []
    for font in plugin.fonts:
        installed_path = _installed_path(font)
        items.append({
            "id": font.font_id,
            "name": font.name,
            "installed": installed_path is not None,
            "path": str(installed_path or font.destination),
        })
    installed = sum(item["installed"] for item in items)
    return {
        "installed": installed,
        "total": len(items),
        "complete": installed == len(items),
        "items": items,
        "error": error,
        "log": str(FONT_LOG),
    }


def _fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "Lexeditor/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        length = response.headers.get("Content-Length")
        if length and int(length) > MAX_FONT_BYTES:
            raise ValueError(f"font is larger than {MAX_FONT_BYTES} bytes")
        payload = response.read(MAX_FONT_BYTES + 1)
    if len(payload) > MAX_FONT_BYTES:
        raise ValueError(f"font is larger than {MAX_FONT_BYTES} bytes")
    return payload


def _log_failure(plugin: GamePlugin, font: PluginFont, error: Exception,
                 log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    message = (
        f"{stamp} plugin={plugin.plugin_id} font={font.font_id} "
        f"url={font.source_url} error={type(error).__name__}: {error}\n"
    )
    with _LOG_LOCK, log_path.open("a", encoding="utf-8") as stream:
        stream.write(message)


def _install(font: PluginFont, fetcher: FontFetcher) -> None:
    payload = fetcher(font.source_url)
    digest = hashlib.sha256(payload).hexdigest()
    if digest.casefold() != font.sha256.casefold():
        raise ValueError(f"SHA-256 mismatch: expected {font.sha256}, got {digest}")
    if len(payload) < 44 or payload[:4] not in _FORMAT_MAGIC[font.file_format]:
        raise ValueError(f"downloaded data is not a {font.file_format} font")
    font.destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", delete=False, dir=font.destination.parent,
            prefix=f".{font.destination.name}.", suffix=".tmp",
        ) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(font.destination)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def install_missing_fonts(plugin: GamePlugin, fetcher: FontFetcher = _fetch,
                          log_path: Path = FONT_LOG) -> dict:
    """Install missing fonts, log each failure, and never block the plugin."""
    errors = []
    for font in plugin.fonts:
        if _installed_path(font) is not None:
            continue
        try:
            _install(font, fetcher)
        except Exception as error:
            _log_failure(plugin, font, error, log_path)
            errors.append(f"{font.name}: {error}")
    message = "; ".join(errors)
    result = font_status(plugin, message)
    result["errors"] = errors
    return result
