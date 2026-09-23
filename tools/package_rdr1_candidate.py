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
ROOT_RUNTIME_SUFFIXES = {".py", ".txt", ".cmd", ".ps1"}
RDR_TEST_TOOLS = {
    "tools/package_rdr1_candidate.py",
    "tools/rdr_test_support.py",
    "tools/verify_rdr_editing.py",
    "tools/verify_rdr_cache_reuse_71.py",
    "tools/verify_rdr_items_split_issue_19.py",
    "tools/verify_rdr_data_map_audit.py",
    "tools/verify_rdr_mod_compatibility.py",
    "tests/test_rdr_string_tables.py",
    "tests/test_rdr_rbf.py",
    "tools/magic-rdr/README.md",
}
FONT_SUFFIXES = {".ttf", ".otf", ".woff", ".woff2"}
REQUIRED = (
    "app.py",
    "plugins/rdr/plugin.py",
    "plugins/rdr/server.py",
    "plugins/rdr/editor.html",
    "plugins/rdr/editor.css",
    "plugins/rdr/editor.js",
    "plugins/rdr/strings.js",
    "plugins/rdr/string_tables.py",
    "plugins/rdr/rbf.js",
    "plugins/rdr/rbf.py",
    "plugins/rdr/magic_rdr_manager.py",
    "tools/magic-rdr/README.md",
)


def _candidate_path(path: PurePosixPath) -> bool:
    text = path.as_posix()
    if any(path == prefix or prefix in path.parents for prefix in OMIT_PREFIXES):
        return False
    if path.suffix.casefold() in FONT_SUFFIXES:
        return False
    if len(path.parts) == 1:
        return path.suffix.casefold() in ROOT_RUNTIME_SUFFIXES or text in {
            "README.md", "pytest.ini",
        }
    if text == "plugins/__init__.py" or path.parts[:2] == ("plugins", "rdr"):
        return True
    if path.parts[0] == "ui":
        return not text.startswith("ui/assets/blank-game")
    if path.parts[0] == "assets":
        return text in {"assets/lexeditor.ico", "assets/lexeditor.png"}
    return text in RDR_TEST_TOOLS


def tracked_files(root: Path) -> list[PurePosixPath]:
    payload = subprocess.check_output(["git", "-C", str(root), "ls-files", "-z"])
    paths = []
    for raw in payload.split(b"\0"):
        if not raw:
            continue
        path = PurePosixPath(raw.decode("utf-8"))
        if _candidate_path(path):
            paths.append(path)
    return sorted(paths, key=str)


def _candidate_bytes(root: Path, relative: PurePosixPath) -> bytes:
    target = (root / Path(*relative.parts)).resolve()
    if not target.is_file():
        raise RuntimeError(f"Tracked candidate file is unavailable: {relative}")
    if relative.as_posix() in {
        "ui/credits.json", "ui/credits-sources.json", "ui/mod-loading.json",
    }:
        document = json.loads(target.read_text(encoding="utf-8-sig"))
        plugins = document.get("plugins")
        if isinstance(plugins, dict) and "rdr" in plugins:
            document["plugins"] = {"rdr": plugins["rdr"]}
        return (json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    return target.read_bytes()


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
            "redHookInstall": "manual-official-download-only",
            "realGameAcceptanceSeparate": True,
        },
        "files": len(files),
        "scope": {
            "gamePlugins": ["rdr"],
            "sharedRuntime": True,
            "sharedUI": True,
            "rdrAcceptanceTools": True,
            "otherGamePlugins": False,
            "fontFiles": False,
        },
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative in files:
            archive.writestr(str(relative), _candidate_bytes(root, relative))
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
                "This candidate contains only plugins/rdr; its copied Credits/Mod Loading metadata "
                "is narrowed to that plugin so shared discovery remains valid.\n"
                "RDR_GAME_ROOT may point at the installed game; preparation reads source "
                "archives and writes only the isolated cache/project until Deploy Project "
                "is explicitly invoked.\n\n"
                "Exact Windows PowerShell acceptance setup (edit paths for your machine):\n"
                "  $env:LEXEDITOR_RDR_RPF6_TOOL = 'C:\\Lexeditor\\tools\\magic-rdr\\app\\Rpf6ReadCli.exe'\n"
                "  $env:LEXEDITOR_RDR_RPF6_NAMES = 'C:\\Lexeditor\\tools\\magic-rdr\\app\\Settings\\ImportedFileNames.txt'\n"
                "  $env:LEXEDITOR_RDR_PROJECT = \"$PWD\\_rdr-project\"\n"
                "  $env:LEXEDITOR_RDR_EXTRACT_ROOT = \"$PWD\\_rdr-cache\"\n"
                "  $env:RDR_GAME_ROOT = 'D:\\SteamLibrary\\steamapps\\common\\Red Dead Redemption'\n"
                "  python .\\app.py\n\n"
                "Acceptance checklist:\n"
                "  1. Home: MagicRDR bridge is present, pinned to v1.3.10, and has no install/auto-update action.\n"
                "  2. Open RDR1 and prepare data. No source game archive is rewritten.\n"
                "  3. Strings: language tabs appear before resource selection; search spans resources; Resource shows the owning STRTBL path.\n"
                "  4. Edit one string, Save, switch to Vanilla and back, then reload: Vanilla stays unchanged and the project text reopens.\n"
                "  5. Make another unsaved string edit and Discard string edits: the last saved text returns.\n"
                "  6. Data Map: supported PC STRTBL and actual parsed RBF0 scalar rows are Partial/openable; _ps3 STRTBL, unsafe RBF0 content and unknown formats remain visible as Not integrated.\n"
                "  7. Tuning (RBF0): edit one bool/uint32/float leaf, Save, switch Vanilla/back, then verify only the project override changes; strings, vectors, byte blocks and unknown records stay opaque.\n"
                "  8. Items/Shops/Missions/Tweaks: change one safe field, Save, reopen, and confirm the project override without changing prepared source bytes.\n"
                "  9. Info: if RedHook is absent, Keep editing works and Open official download only opens the official page. RedHook is never bundled or silently installed.\n"
                "  10. Do not click Deploy Project for source/rendered acceptance. Deployment and in-game behavior are separate acceptance levels.\n"
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
        other_games = sorted(
            name for name in names
            if name.startswith("plugins/") and not (
                name == "plugins/__init__.py" or name.startswith("plugins/rdr/")
            )
        )
        if other_games:
            raise RuntimeError("Candidate contains another game plugin")
        fonts = sorted(
            name for name in names
            if PurePosixPath(name).suffix.casefold() in FONT_SUFFIXES
        )
        if fonts:
            raise RuntimeError("Candidate contains font files")
        manifest = json.loads(archive.read("RDR1-CANDIDATE.json"))
        if manifest.get("sourceCommit") != commit:
            raise RuntimeError("Candidate manifest commit does not match the requested commit")
        if not manifest.get("acceptance", {}).get("doNotOverwriteExistingLexeditor"):
            raise RuntimeError("Candidate isolation warning is missing")
        for metadata_name in ("ui/credits.json", "ui/mod-loading.json"):
            metadata = json.loads(archive.read(metadata_name))
            if set(metadata.get("plugins", {})) != {"rdr"}:
                raise RuntimeError(
                    f"Candidate metadata is not narrowed to RDR1: {metadata_name}"
                )
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
