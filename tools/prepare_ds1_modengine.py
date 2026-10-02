"""Prepare source-only corrections for the pinned DSR ModEngine2 launcher.

Usage:
    python tools/prepare_ds1_modengine.py ORIGINAL_LAUNCHER_CPP NEW_OUTPUT_FOLDER

The input must match the reviewed upstream Git blob. CRLF checkout conversion is
accepted, but other changes are not. This emits replacement launcher sources and
the upstream license into a new folder; it neither patches a game nor builds,
downloads, installs or certifies a native runtime. The runtime builder must use
the complete pinned upstream checkout and preserve all dependency notices.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SOURCE_REPOSITORY = "AltimorTASDK/ModEngine2"
SOURCE_REVISION = "76690e95d5022ba6f8d1bc24faea1f1bfde2ec6d"
LAUNCHER_BLOB = "6e79759da92f0a12a7bcefb5a469e85c3414298a"
MAX_SOURCE_BYTES = 128 * 1024
ASSETS = Path(__file__).resolve().parents[1] / "plugins" / "ds1" / "modengine"

MANUAL_OLD = """        app_path = absolute(CLI::to_path(target_path_string)).parent_path().parent_path();
        if (target == AUTODETECT) {
            logger->error("Game target must be specified when supplying a manual path");
            return E_APP_NOT_FOUND;
        }"""
MANUAL_NEW = """        if (target == AUTODETECT) {
            logger->error("Game target must be specified when supplying a manual path");
            return E_APP_NOT_FOUND;
        }
        app_path = lexeditor_ds1::application_root(
            CLI::to_path(target_path_string), launch_targets.at(target).executable_path);"""

REPLACEMENTS = (
    ('#include "steam_app_path.h"',
     '#include "steam_app_path.h"\n#include "lexeditor_launcher_paths.h"'),
    (MANUAL_OLD, MANUAL_NEW),
    ("app_path = exepath.parent_path().parent_path(); // app_path is expected to be steam app path not exe path",
     "app_path = lexeditor_ds1::application_root(exepath, launch_targets.at(target).executable_path);"),
    ("    STARTUPINFOW si = {};\n", "    STARTUPINFOW si = {};\n    si.cb = sizeof(si);\n"),
    ("""    if (!success) {
        logger->error("Couldn't create process: {:x}", GetLastError());
    }""",
     """    if (!success) {
        logger->error("Couldn't create process: {:x}", GetLastError());
        return E_OS_ERROR;
    }"""),
)


def git_blob_hash(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def patch_launcher(data: bytes) -> bytes:
    """Return the audited patch, or refuse any source other than the pinned blob."""
    if len(data) > MAX_SOURCE_BYTES:
        raise ValueError("Launcher source exceeds the size limit")
    canonical = data.replace(b"\r\n", b"\n")
    if git_blob_hash(canonical) != LAUNCHER_BLOB:
        raise ValueError("Launcher source does not match the pinned ModEngine2 revision")
    source = canonical.decode("utf-8")
    for before, after in REPLACEMENTS:
        if source.count(before) != 1:
            raise ValueError("Launcher patch anchor did not match exactly once")
        source = source.replace(before, after, 1)
    return source.encode("utf-8")


def prepare_launcher(source: Path, destination: Path) -> dict:
    """Emit only to a newly claimed directory; preserve the upstream input."""
    with Path(source).open("rb") as stream:
        patched = patch_launcher(stream.read(MAX_SOURCE_BYTES + 1))
    outputs = {
        "launcher.cpp": patched,
        "lexeditor_launcher_paths.h": (ASSETS / "lexeditor_launcher_paths.h").read_bytes(),
        "LICENSE-MIT": (ASSETS / "LICENSE-MIT").read_bytes(),
    }
    manifest = {
        "schema": 1,
        "sourceRepository": SOURCE_REPOSITORY,
        "sourceRevision": SOURCE_REVISION,
        "originalLauncherGitBlob": LAUNCHER_BLOB,
        "nativeBuildVerified": False,
        "files": {name: hashlib.sha256(data).hexdigest() for name, data in outputs.items()},
    }
    destination = Path(destination)
    # An explicit, one-off developer export, not an automatic cache or history.
    destination.mkdir()  # Existing files/directories are never overwritten.
    for name, data in outputs.items():
        with (destination / name).open("xb") as stream:
            stream.write(data)
    # Publish the manifest last. An interrupted preparation has no completion marker.
    with (destination / "source-patch.json").open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2)
        stream.write("\n")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        manifest = prepare_launcher(args.source, args.destination)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Cannot prepare DSR launcher sources: {error}\n")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
