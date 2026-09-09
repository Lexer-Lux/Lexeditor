"""Safe per-resource inspection for Chrono Trigger project/archive data."""

from __future__ import annotations

import hashlib
import mimetypes
from pathlib import PurePosixPath

from .data import OverlayStore, classify_resource, normalize_virtual_path


MAX_RESOURCE_BYTES = 32 * 1024 * 1024
MAX_TEXT_PREVIEW_BYTES = 128 * 1024
_TEXT_SUFFIXES = {".txt", ".json", ".cfg", ".ini", ".csv", ".md", ".xml"}
_IMAGE_SUFFIXES = {".png", ".bmp", ".gif", ".jpg", ".jpeg", ".webp"}


def read_resource(store: OverlayStore, virtual_path: str, source: str = "mine") -> tuple[bytes, str, str]:
    virtual = normalize_virtual_path(virtual_path)
    data, origin = store.read(virtual, source)
    if len(data) > MAX_RESOURCE_BYTES:
        raise RuntimeError(
            f"Decoded resource is too large for direct inspection: {len(data)} bytes "
            f"(limit {MAX_RESOURCE_BYTES})"
        )
    return data, origin, virtual


def resource_info(store: OverlayStore, virtual_path: str, source: str = "mine") -> dict:
    data, origin, virtual = read_resource(store, virtual_path, source)
    suffix = PurePosixPath(virtual).suffix.casefold()
    content_type = mimetypes.guess_type(virtual)[0] or "application/octet-stream"
    preview_kind = "image" if suffix in _IMAGE_SUFFIXES else "text" if suffix in _TEXT_SUFFIXES else "binary"
    preview = None
    preview_truncated = False
    decode_error = None
    if preview_kind == "text":
        sample = data[:MAX_TEXT_PREVIEW_BYTES]
        preview_truncated = len(data) > len(sample)
        try:
            preview = sample.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            preview_kind = "binary"
            decode_error = str(error)
    return {
        "kind": "resource-info",
        "path": virtual,
        "source": origin,
        "readOnly": source == "vanilla",
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "suffix": suffix,
        "contentType": content_type,
        "previewKind": preview_kind,
        "preview": preview,
        "previewTruncated": preview_truncated,
        "decodeError": decode_error,
        **classify_resource(virtual),
    }
