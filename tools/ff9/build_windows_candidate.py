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

from plugins.ff9 import memoria_manager
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

    runtime_source = ROOT / "plugins" / "ff9" / "runtime" / RUNTIME_NAME
    if not runtime_source.is_file():
        raise FileNotFoundError(f"FF9 runtime is missing: {runtime_source}")
    runtime_target = internal / "plugins" / "ff9" / "runtime" / RUNTIME_NAME
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

    acceptance = OUT / "FF9-ACCEPTANCE.txt"
    acceptance.write_text(
        "FF9 Lexeditor isolated acceptance candidate\n"
        "===========================================\n\n"
        "This artifact is for installed-game acceptance only. It keeps its own "
        "LOCALAPPDATA and FF9 project beside the extracted candidate.\n\n"
        "1. Extract the entire artifact to a writable folder. Do not run it from inside the ZIP.\n"
        "2. Close FINAL FANTASY IX, its launcher, Memoria tools, and any installed Lexeditor window.\n"
        "3. Run Launch-FF9-Candidate.cmd and pass the FF9 Steam install folder as the first argument "
        "if auto-detection does not find it. Example:\n"
        "   Launch-FF9-Candidate.cmd \"D:\\\\SteamLibrary\\\\steamapps\\\\common\\\\FINAL FANTASY IX\"\n"
        "4. Open Final Fantasy 9 in Lexeditor. In the Updates/Info helper controls, install or repair "
        "the pinned Memoria helper if it is not reported installed. Confirm automatic updates are disabled.\n"
        "5. Open Enemies or Encounters. Change one obvious, reversible value (for example an enemy HP value "
        "or one encounter rate), then Save.\n"
        "6. Reopen that record before deployment and confirm the saved value is still present.\n"
        "7. Use Deploy Project. Launch the game through the normal FF9 launcher/Memoria path from Lexeditor.\n"
        "8. Reach the affected battle and confirm the edited behavior/value is active in game.\n"
        "9. Return to Lexeditor and Revert/remove the deployed project. Confirm unrelated Memoria settings "
        "and other mods remain intact, then relaunch and confirm the edited behavior is gone.\n\n"
        "FIELD WALKMESH NATIVE CHECK (optional; use only a disposable/backup save and a known safe field/floor/triangle)\n"
        "- In World -> Field walkmesh floors or Field walkmesh triangles, choose one pathing element whose normal active state is known and whose "
        "navigation can be tested without risking progression. Change only the Active switch, Save, reopen, Deploy, "
        "enter or reload that field, and confirm the chosen pathing element is enabled/disabled as expected.\n"
        "- Revert, relaunch/reload, and confirm the original pathing behavior returns. If no safe observable floor/triangle "
        "is available, report BGI native behavior as not tested rather than inferring it from CI.\n\n"
        "EXTERNAL MOD COMPATIBILITY (run on a disposable/backup profile if external mods are present)\n"
        "- Open Information -> External Mod Compatibility. Record enabled mods, unsupported-runtime entries, "
        "declared conflicts, and exact-path overlaps before deployment.\n"
        "- With an already-installed compatible Memoria mod enabled, record its FolderNames position and, if "
        "Priorities exists, its Priorities position, and hash or copy one representative file. "
        "Deploy Lexeditor: Lexeditor must become first while the other "
        "mod's folder and bytes remain unchanged. Revert: only Lexeditor must disappear and the prior external "
        "order/bytes must remain.\n"
        "- If a safe test profile intentionally contains the same Lexeditor-generated CSV, battle raw16, or field-walkmesh BGI path "
        "in Lexeditor and an external mod, the deployed Lexeditor file must win because FolderNames is "
        "highest-priority first. Revert must expose the external file again. Do not generalize this result to "
        "Memoria patch-file families that compose low-to-high or to event scripts, which have separate append/"
        "MergeScripts behavior.\n"
        "- Do not count mods whose ModDescription.xml requires a Memoria version newer than the candidate's pinned "
        "v2025.07.04 as supported. The 2026-09-22 catalog audit found Ferny Fantasy IX, MistwakeUI - English "
        "Version, CostumePack 2.1, and Extra Equipment Menu 1.2 beyond that pin. Mods with no "
        "MinimumMemoriaVersion declaration remain runtime-compatibility UNKNOWN until native testing.\n\n"
        "Report separately: helper install/repair, save/reopen, baseline deployment, native battle behavior, "
        "BGI floor/triangle behavior (if safely tested), revert, compatible-mod coexistence, exact-path overlap (if tested), "
        "and any error text shown.\n",
        encoding="utf-8",
    )

    manifest = {
        "headSha": os.environ.get("LEXEDITOR_CANDIDATE_HEAD_SHA", ""),
        "artifactPurpose": "FF9 installed-game acceptance only",
        "isolatedLocalAppData": str(local_appdata.relative_to(OUT)),
        "isolatedProject": "FF9-project",
        "acceptanceGuide": acceptance.name,
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
