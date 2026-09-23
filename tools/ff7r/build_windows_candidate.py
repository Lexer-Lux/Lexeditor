"""Build a disposable Windows FF7R acceptance candidate.

The normal reviewed frozen application is copied into an isolated folder. The
launcher redirects LOCALAPPDATA plus FF7R project/cache state beside the
candidate, so it never reuses or overwrites an installed C:\\Lexeditor tree.
The build also verifies that the redistribution-cleared repak v0.2.3 release
archive and both upstream licence files survived freezing.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from plugins.ff7r import tooling
from tools import build_distribution

OUT = ROOT / "out" / "ff7r-windows-candidate"


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def verify_windows_repak(bundle: Path) -> dict:
    manifest_path = bundle / "manifest.json"
    archive = bundle / "repak_cli-x86_64-pc-windows-msvc.zip"
    mit = bundle / "LICENSE-MIT"
    apache = bundle / "LICENSE-APACHE"
    for path in (manifest_path, archive, mit, apache):
        if not path.is_file():
            raise FileNotFoundError(f"Frozen FF7R helper payload is missing: {path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    row = manifest["platforms"]["win32"]
    archive_sha = digest(archive)
    if archive_sha != row["archiveSha256"]:
        raise RuntimeError("Frozen repak archive does not match the pinned release SHA-256")
    if archive_sha != tooling.BUNDLES["win32"][1]:
        raise RuntimeError("Frozen repak archive disagrees with the runtime pin")

    with zipfile.ZipFile(archive) as package:
        matches = [
            name for name in package.namelist()
            if name.rsplit("/", 1)[-1].casefold() == "repak.exe"
        ]
        if len(matches) != 1:
            raise RuntimeError("Pinned repak archive must contain exactly one repak.exe")
        executable = package.read(matches[0])
    executable_sha = digest_bytes(executable)
    if executable_sha != row["executableSha256"]:
        raise RuntimeError("Frozen repak executable does not match the pinned SHA-256")

    source = tooling.BUNDLE_ROOT
    for name in ("manifest.json", "LICENSE-MIT", "LICENSE-APACHE"):
        if (bundle / name).read_bytes() != (source / name).read_bytes():
            raise RuntimeError(f"Frozen repak notice changed during packaging: {name}")

    return {
        "version": manifest["tag"],
        "source": manifest["source"],
        "releaseCommit": manifest["commit"],
        "archive": str(archive),
        "archiveSha256": archive_sha,
        "executableSha256": executable_sha,
        "licenses": ["LICENSE-MIT", "LICENSE-APACHE"],
    }


def main() -> None:
    if os.name != "nt":
        raise RuntimeError("The FF7R acceptance candidate must be built on Windows")
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

    frozen_bundle = internal / "plugins" / "ff7r" / "runtime" / "repak" / tooling.REPAK_TAG
    helper = verify_windows_repak(frozen_bundle)

    local_appdata = OUT / "candidate-localappdata"
    project = OUT / "FF7R-project"
    data = OUT / "FF7R-data"
    for directory in (local_appdata, project, data):
        directory.mkdir(parents=True, exist_ok=True)

    launcher = OUT / "Launch-FF7R-Candidate.cmd"
    launcher.write_text(
        "@echo off\r\n"
        "setlocal\r\n"
        "set \"LOCALAPPDATA=%~dp0candidate-localappdata\"\r\n"
        "set \"LEXEDITOR_FF7R_PROJECT=%~dp0FF7R-project\"\r\n"
        "set \"LEXEDITOR_FF7R_DATA_ROOT=%~dp0FF7R-data\"\r\n"
        "if not \"%~1\"==\"\" set \"LEXEDITOR_FF7R_ROOT=%~f1\"\r\n"
        "start \"\" \"%~dp0Lexeditor\\Lexeditor.exe\"\r\n",
        encoding="utf-8",
    )

    acceptance = OUT / "FF7R-ACCEPTANCE.txt"
    acceptance.write_text(
        "FINAL FANTASY VII REMAKE INTERGRADE isolated Lexeditor candidate\n"
        "==============================================================\n\n"
        "Purpose: installed-game acceptance only. Source CI and rendered fixture "
        "screenshots do not prove retail PAK parsing or gameplay behavior.\n\n"
        "1. Extract the entire artifact to a NEW writable folder. Do not overlay "
        "C:\\Lexeditor or another Lexeditor installation.\n"
        "2. Close FF7R and any installed Lexeditor window. Run "
        "Launch-FF7R-Candidate.cmd. If auto-detection misses the game, pass the "
        "FF7R install folder as the first argument. Example:\n"
        "   Launch-FF7R-Candidate.cmd \"D:\\SteamLibrary\\steamapps\\common\\"
        "FINAL FANTASY VII REMAKE INTERGRADE\"\n"
        "3. Open FF7R. In Updates/Info, confirm repak is pinned to v0.2.3, the "
        "bundled package reports verified, and Install/Repair installs it into "
        "this candidate's LOCALAPPDATA only. No helper download should occur.\n"
        "4. Data Map: open representative Resident DataObjects and one Text "
        "resource. Record which rows are Structured/Partial versus read-only "
        "research views. Unsupported fields must remain locked/preserved.\n"
        "5. Change one reversible DataObject value and one text value, Save, "
        "restart the candidate, and confirm both project overlays reopen while "
        "the installed game archives remain unchanged. Exercise Undo/Redo and "
        "Discard before and after the saved baseline.\n"
        "6. Build Project. Confirm FF7R-project\\build\\Lexeditor-FF7R_P.pak "
        "is produced. Do not count this as in-game success.\n"
        "7. If testing deployment, first record existing End\\Content\\Paks\\~mods "
        "contents. Deploy only explicitly. An unmanaged existing "
        "Lexeditor-FF7R_P.pak must be refused; a managed unchanged Lexeditor PAK "
        "may be replaced/removed. After Remove deployed PAK, unrelated mod files "
        "and their hashes must be unchanged.\n"
        "8. For a real third-party PAK you are licensed to use, use Mod Loading "
        "Find/Add on a disposable profile. Record its package filename and listed "
        "asset paths. Lexeditor must report exact asset overlap with another "
        "selected/existing PAK as a conflict instead of silently choosing a load "
        "order. Remove/revert must restore the prior managed deployment bytes.\n"
        "9. Run issue-specific retail checks separately: #415 shop prices/carry "
        "cap, #416 normal/rare/steal drops, and #413 cutscene speed/R2 composition. "
        "Do not infer those results from this candidate's source or UI behavior.\n\n"
        "Report separately: helper packaging/install, source reads, rendered UI, "
        "save/reopen, build, third-party mod coexistence/conflict, deployment/"
        "restoration, and actual in-game behavior.\n",
        encoding="utf-8",
    )

    manifest = {
        "headSha": os.environ.get("LEXEDITOR_CANDIDATE_HEAD_SHA", ""),
        "artifactPurpose": "FF7R installed-game acceptance only",
        "frozenAppSmokePassed": True,
        "isolatedLocalAppData": str(local_appdata.relative_to(OUT)),
        "isolatedProject": str(project.relative_to(OUT)),
        "isolatedDataCache": str(data.relative_to(OUT)),
        "launcher": launcher.name,
        "acceptanceGuide": acceptance.name,
        "repak": {
            **helper,
            "archive": str(Path(helper["archive"]).relative_to(OUT)),
        },
        "productionDistributionIncludesPinnedRepak": True,
        "retailGameAcceptance": False,
    }
    (OUT / "candidate-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
