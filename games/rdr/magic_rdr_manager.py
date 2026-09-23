"""Read-only MagicRDR bridge status and upstream release checks.

MagicRDR's public repository declares no redistribution license. Lexeditor may
use an existing local bridge, but this module never downloads, installs, replaces,
or updates MagicRDR bytes.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import urllib.request

from . import paths


PINNED_RELEASE = "v1.3.10"
REPOSITORY = "https://github.com/Foxxyyy/Magic-RDR"
LATEST_RELEASE_API = "https://api.github.com/repos/Foxxyyy/Magic-RDR/releases/latest"


def status(tool: Path | None = None, names: Path | None = None) -> dict:
    tool_path = Path(tool or paths.RPF6_TOOL)
    names_path = Path(names or paths.RPF6_NAMES)
    tool_ok = tool_path.is_file()
    names_ok = names_path.is_file()
    installed = tool_ok and names_ok
    missing = []
    if not tool_ok:
        missing.append(str(tool_path))
    if not names_ok:
        missing.append(str(names_path))
    return {
        "runtime": "MagicRDR bridge",
        "pinned": PINNED_RELEASE,
        "source": REPOSITORY,
        "installed": installed,
        "present": tool_ok or names_ok,
        "version": PINNED_RELEASE if installed else "",
        "integrity": "present" if installed else "incomplete" if tool_ok or names_ok else "not-installed",
        "autoUpdate": False,
        "installable": False,
        "tool": str(tool_path),
        "names": str(names_path),
        "missing": missing,
        "message": (
            "Pinned local MagicRDR bridge is available; automatic install/update is disabled."
            if installed else
            "MagicRDR is intentionally not bundled. Point Lexeditor at an existing local "
            "Rpf6ReadCli.exe and ImportedFileNames.txt to prepare RDR1 archive data."
        ),
    }


def _fetch_json(url: str) -> dict:
    request = urllib.request.Request(
        url, headers={"Accept": "application/vnd.github+json", "User-Agent": "Lexeditor-RDR1/1"})
    with urllib.request.urlopen(request, timeout=15) as response:
        raw = response.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise RuntimeError("MagicRDR release metadata is too large.")
    return json.loads(raw)


def _version(value: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", value.strip())
    if not match:
        raise ValueError(f"Unsupported MagicRDR release tag: {value!r}")
    return tuple(map(int, match.groups()))


def upstream_release(fetch_json=None) -> dict:
    """Report newest stable upstream release; never install or change the pin."""
    base = {
        "runtime": "MagicRDR bridge",
        "pinned": PINNED_RELEASE,
        "source": REPOSITORY,
        "installable": False,
        "autoUpdate": False,
    }
    try:
        payload = (fetch_json or _fetch_json)(LATEST_RELEASE_API)
        latest = str(payload.get("tag_name", ""))
        latest_version = _version(latest)
        if payload.get("draft") or payload.get("prerelease"):
            raise RuntimeError("Upstream did not return a stable MagicRDR release.")
        return {
            **base,
            "latest": latest,
            "published": str(payload.get("published_at", "")),
            "releaseNotes": REPOSITORY + "/releases/tag/" + latest,
            "behind": latest_version > _version(PINNED_RELEASE),
        }
    except Exception as error:
        return {**base, "behind": False, "error": str(error)}
