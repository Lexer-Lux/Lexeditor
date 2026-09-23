"""Build a disposable Windows FF9 acceptance candidate.

The production distribution helper allowlist intentionally stays unchanged. This
script builds the normal reviewed app, then adds the FF9 runtime DLL and audited
Memoria patcher only to the workflow artifact. The launcher redirects LOCALAPPDATA
and the FF9 project into the extracted candidate directory so testing does not
reuse the installed Lexeditor state.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from games.ff9 import memoria_manager
from tools import build_distribution

OUT = ROOT / "out" / "ff9-windows-candidate"
RUNTIME_NAME = "Memoria.Scripts.Lexeditor.dll"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> None:
    if os.name != "nt":
        raise RuntimeError("The FF9 acceptance candidate must be built on Windows")
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    executable = build_distribution.build_app()
    build_distribution.smoke(executable)

    app_root = OUT / "Lexeditor"
    shutil.copytree(executable.parent, app_root)

    internal = app_root / "_internal"
    if not internal.is_dir():
        raise RuntimeError("Unexpected PyInstaller onedir layout: _internal is missing")

    runtime_source = ROOT / "games" / "ff9" / "runtime" / RUNTIME_NAME
    if not runtime_source.is_file():
        raise FileNotFoundError(f"FF9 runtime is missing: {runtime_source}")
    runtime_target = internal / "games" / "ff9" / "runtime" / RUNTIME_NAME
    runtime_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(runtime_source, runtime_target)
    if digest(runtime_target) != digest(runtime_source):
        raise RuntimeError("Candidate FF9 runtime copy failed verification")

    local_appdata = OUT / "candidate-localappdata"
    cache = local_appdata / "Lexeditor" / "helpers" / "downloads"
    patcher, published = memoria_manager.stage(cache_root=cache)
    if digest(patcher) != memoria_manager.PINNED_ASSET_SHA256:
        raise RuntimeError("Candidate Memoria patcher does not match the pinned SHA-256")

    project = OUT / "FF9-project" / "StreamingAssets" / "Data"
    project.mkdir(parents=True)

    launcher = OUT / "Launch-FF9-Candidate.cmd"
    launcher.write_text(
        "@echo off\r\n"
        "setlocal\r\n"
        "set \"LOCALAPPDATA=%~dp0candidate-localappdata\"\r\n"
        "set \"LEXEDITOR_FF9_PROJECT=%~dp0FF9-project\"\r\n"
        "if not \"%~1\"==\"\" set \"LEXEDITOR_FF9_ROOT=%~f1\"\r\n"
        "if not exist \"%LEXEDITOR_FF9_PROJECT%\\StreamingAssets\\Data\" "
        "mkdir \"%LEXEDITOR_FF9_PROJECT%\\StreamingAssets\\Data\"\r\n"
        "start \"\" \"%~dp0Lexeditor\\Lexeditor.exe\"\r\n",
        encoding="utf-8",
    )

    manifest = {
        "headSha": os.environ.get("LEXEDITOR_CANDIDATE_HEAD_SHA", ""),
        "artifactPurpose": "FF9 installed-game acceptance only",
        "isolatedLocalAppData": str(local_appdata.relative_to(OUT)),
        "isolatedProject": "FF9-project",
        "runtime": {
            "path": str(runtime_target.relative_to(OUT)),
            "sha256": digest(runtime_target),
        },
        "memoria": {
            "version": published["version"],
            "path": str(patcher.relative_to(OUT)),
            "sha256": digest(patcher),
            "publisherUrl": published["url"],
        },
        "productionHelperAllowlistModified": False,
    }
    (OUT / "candidate-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
