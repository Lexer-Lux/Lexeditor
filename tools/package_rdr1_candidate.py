"""Build a license-safe isolated RDR1 Lexeditor source candidate.

The repository contains a pinned MagicRDR installation whose upstream repository
does not declare redistribution terms. Candidate archives therefore omit those
binaries and bridge source instead of repackaging them. A tester may point the
candidate at an existing local pinned bridge with the documented environment
variables; that source installation is only read, never modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import zipfile


OMIT_PREFIXES = (
    PurePosixPath("tools/magic-rdr/app"),
    PurePosixPath("tools/magic-rdr/cli"),
    PurePosixPath("tools/magic-rdr/source"),
)
REQUIRED = (
    "app.py",
    "games/rdr/plugin.py",
    "games/rdr/server.py",
    "games/rdr/editor.html",
    "games/rdr/assets/editor.css",
    "games/rdr/assets/editor.js",
    "games/rdr/assets/strings.js",
    "games/rdr/string_tables.py",
    "tools/magic-rdr/README.md",
)


def tracked_files(root: Path) -> list[PurePosixPath]:
    payload = subprocess.check_output(["git", "-C", str(root), "ls-files", "-z"])
    paths = []
    for raw in payload.split(b"\0"):
        if not raw:
            continue
        path = PurePosixPath(raw.decode("utf-8"))
        if any(path == prefix or prefix in path.parents for prefix in OMIT_PREFIXES):
            continue
        paths.append(path)
    return sorted(paths, key=str)


def build(root: Path, output: Path, commit: str) -> dict:
    root = root.resolve()
    output = output.resolve()
    files = tracked_files(root)
    names = {str(path) for path in files}
    missing = [path for path in REQUIRED if path not in names]
    if missing:
        raise RuntimeError("Candidate is missing required tracked files: " + ", ".join(missing))

    manifest = {
        "schemaVersion": 1,
        "candidate": "RDR1 Plugin",
        "sourceCommit": commit,
        "sourceBranch": "codex/rdr1-plugin-completion",
        "pullRequest": 487,
        "isolated": True,
        "omittedRedistribution": [
            "tools/magic-rdr/app/**",
            "tools/magic-rdr/cli/**",
            "tools/magic-rdr/source",
        ],
        "externalHelper": {
            "reason": (
                "MagicRDR has no declared repository license; the candidate does "
                "not repackage its binaries or source."
            ),
            "toolEnv": "LEXEDITOR_RDR_RPF6_TOOL",
            "namesEnv": "LEXEDITOR_RDR_RPF6_NAMES",
            "expectedTool": "Rpf6ReadCli.exe",
            "expectedNames": "Settings/ImportedFileNames.txt",
        },
        "acceptance": {
            "extractToNewDirectory": True,
            "doNotOverwriteExistingLexeditor": True,
            "projectEnv": "LEXEDITOR_RDR_PROJECT",
            "dataEnv": "LEXEDITOR_RDR_EXTRACT_ROOT",
            "gameEnv": "RDR_GAME_ROOT",
        },
        "files": len(files),
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative in files:
            target = (root / Path(*relative.parts)).resolve()
            if not target.is_file():
                raise RuntimeError(f"Tracked candidate file is unavailable: {relative}")
            archive.write(target, str(relative))
        archive.writestr(
            "RDR1-CANDIDATE.json",
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        )
        archive.writestr(
            "RDR1-CANDIDATE.txt",
            (
                "RDR1 Plugin isolated candidate\n"
                f"Source commit: {commit}\n"
                "PR: https://github.com/Lexer-Lux/Lexeditor/pull/487\n\n"
                "Extract this ZIP to a NEW directory; do not overlay C:\\Lexeditor "
                "or another installation. The MagicRDR helper is intentionally omitted.\n"
                "To reuse an existing pinned local helper without modifying it, set:\n"
                "  LEXEDITOR_RDR_RPF6_TOOL=<existing>\\tools\\magic-rdr\\app\\Rpf6ReadCli.exe\n"
                "  LEXEDITOR_RDR_RPF6_NAMES=<existing>\\tools\\magic-rdr\\app\\Settings\\ImportedFileNames.txt\n"
                "Use an isolated LEXEDITOR_RDR_PROJECT and LEXEDITOR_RDR_EXTRACT_ROOT.\n"
                "RDR_GAME_ROOT may point at the installed game; preparation reads source "
                "archives and writes only the isolated cache/project until Deploy Project "
                "is explicitly invoked.\n"
            ),
        )

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    return {**manifest, "archive": output.name, "sha256": digest}


def verify(archive_path: Path, commit: str) -> dict:
    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        for required in REQUIRED:
            if required not in names:
                raise RuntimeError(f"Candidate archive omitted required file: {required}")
        forbidden = [
            name for name in names
            if any(
                PurePosixPath(name) == prefix or prefix in PurePosixPath(name).parents
                for prefix in OMIT_PREFIXES
            )
        ]
        if forbidden:
            raise RuntimeError("Candidate redistributed omitted MagicRDR content")
        manifest = json.loads(archive.read("RDR1-CANDIDATE.json"))
        if manifest.get("sourceCommit") != commit:
            raise RuntimeError("Candidate manifest commit does not match the requested commit")
        if not manifest.get("acceptance", {}).get("doNotOverwriteExistingLexeditor"):
            raise RuntimeError("Candidate isolation warning is missing")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    result = build(args.root, args.output, args.commit)
    verify(args.output, args.commit)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
