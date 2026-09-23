"""Dependency-explicit FF7 Rebirth IoStore package candidate builder.

This module deliberately does not download tools or Oodle and never writes the
installed game.  It can invoke an explicitly supplied UnrealReZen executable
only after an explicitly supplied Oodle library is present.  Output stays under
the selected Lexeditor project for human/in-game acceptance.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Mapping


UNREALREZEN_ENV = "LEXEDITOR_FF7R2_UNREALREZEN"
OODLE_ENV = "LEXEDITOR_FF7R2_OODLE"
OODLE_NAME = "oo2core_9_win64.dll"
ENGINE_VERSION = "GAME_UE4_26"
MOUNT_POINT = "../../../End/Content/"
PACKAGE_NAME = "Lexeditor-FF7R2_P"
CUE4PARSE_VERSION = "1.1.1"
STAGED_PLAYER = Path("content/End/Content/DataObject/Resident/PlayerParameter.uasset")


class PackagingError(ValueError):
    """A package candidate could not be prepared safely."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _explicit_path(environment: Mapping[str, str], key: str) -> Path | None:
    value = str(environment.get(key, "") or "").strip()
    return Path(value).expanduser() if value else None


def _expected_deps_path(packer: Path) -> Path:
    return packer.with_name(packer.stem + ".deps.json")


def _packer_dependency_ok(packer: Path | None) -> bool:
    if packer is None or not packer.is_file():
        return False
    deps_path = _expected_deps_path(packer)
    if not deps_path.is_file():
        return False
    try:
        payload = json.loads(deps_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    libraries = payload.get("libraries")
    if not isinstance(libraries, dict):
        return False
    return f"CUE4Parse/{CUE4PARSE_VERSION}" in libraries


def _candidate_manifests(project: Path | None) -> list[Path]:
    if project is None:
        return []
    build = project / "build"
    if not build.is_dir():
        return []
    return sorted(build.glob("ff7r2-candidate-*/manifest.json"), key=lambda path: path.stat().st_mtime_ns)


def status(project: Path | None, game: Path | None,
           environment: Mapping[str, str] | None = None) -> dict:
    """Return candidate-builder readiness without executing external software."""
    env = os.environ if environment is None else environment
    packer = _explicit_path(env, UNREALREZEN_ENV)
    oodle = _explicit_path(env, OODLE_ENV)
    staged = project / STAGED_PLAYER if project is not None else None
    paks = game / "End/Content/Paks" if game is not None else None

    packer_present = bool(packer and packer.is_file())
    packer_dependency_ok = _packer_dependency_ok(packer)
    oodle_present = bool(oodle and oodle.is_file())
    expected_oodle = packer.with_name(OODLE_NAME) if packer_present and packer is not None else None
    oodle_in_tool_directory = bool(
        oodle_present
        and expected_oodle is not None
        and expected_oodle.is_file()
        and oodle.resolve() == expected_oodle.resolve()
    )
    staged_present = bool(staged and staged.is_file())
    paks_present = bool(paks and paks.is_dir())
    archives_present = bool(
        paks_present
        and any(paks.glob("*.utoc"))
        and any(paks.glob("*.ucas"))
    )

    missing: list[str] = []
    if project is None:
        missing.append("selected Rebirth project")
    elif not staged_present:
        missing.append(STAGED_PLAYER.as_posix())
    if game is None:
        missing.append("located Rebirth installation")
    elif not archives_present:
        missing.append("Rebirth .utoc/.ucas archives in End/Content/Paks")
    if not packer_present:
        missing.append(f"explicit {UNREALREZEN_ENV} executable")
    elif not packer_dependency_ok:
        missing.append(
            f"UnrealReZen distribution with CUE4Parse/{CUE4PARSE_VERSION} dependency manifest"
        )
    if not oodle_present:
        missing.append(f"explicit {OODLE_ENV} DLL")
    elif not oodle_in_tool_directory:
        missing.append(
            f"{OODLE_NAME} beside the explicit UnrealReZen executable "
            f"(set {OODLE_ENV} to that exact file)"
        )

    manifests = _candidate_manifests(project)
    return {
        "ready": not missing,
        "missing": missing,
        "packerExplicit": packer is not None,
        "packerPresent": packer_present,
        "packerDependencyOk": packer_dependency_ok,
        "packerPath": str(packer) if packer else "",
        "oodleExplicit": oodle is not None,
        "oodlePresent": oodle_present,
        "oodleInToolDirectory": oodle_in_tool_directory,
        "oodlePath": str(oodle) if oodle else "",
        "stagedPresent": staged_present,
        "gameArchivesPresent": archives_present,
        "candidateCount": len(manifests),
        "latestManifest": str(manifests[-1]) if manifests else "",
        "mode": "candidate-only",
        "installsGame": False,
        "downloadsDependencies": False,
        "requiredCUE4Parse": CUE4PARSE_VERSION,
    }


def _plan(project: Path | None, game: Path | None,
          environment: Mapping[str, str]) -> tuple[Path, Path, Path, Path, Path]:
    state = status(project, game, environment)
    if not state["ready"]:
        raise PackagingError(
            "Package candidate is not ready: " + "; ".join(state["missing"])
        )
    assert project is not None and game is not None
    packer = Path(state["packerPath"]).resolve()
    oodle = Path(state["oodlePath"]).resolve()
    deps = _expected_deps_path(packer).resolve()
    content_root = (project / "content/End/Content").resolve()
    paks = (game / "End/Content/Paks").resolve()
    return packer, oodle, deps, content_root, paks


def build_candidate(project: Path | None, game: Path | None,
                    environment: Mapping[str, str] | None = None,
                    runner=subprocess.run) -> dict:
    """Build an isolated, never-installed IoStore candidate.

    UnrealReZen's FF7R2 release loads CUE4Parse Oodle at startup even when
    package compression is Zlib.  Its CUE4Parse/1.1.1 helper returns immediately
    when oo2core_9_win64.dll already exists and otherwise enters its downloader.
    Lexeditor therefore requires that exact dependency manifest and requires
    the explicitly supplied DLL to already be named oo2core_9_win64.dll beside
    UnrealReZen.exe before process start. Lexeditor does not copy, download or
    relocate Oodle, and runs the tool from that directory so both documented
    local-DLL lookup interpretations resolve to the supplied file.
    """
    env = dict(os.environ if environment is None else environment)
    packer, oodle, deps, content_root, game_paks = _plan(project, game, env)
    assert project is not None

    build_root = project / "build"
    build_root.mkdir(parents=True, exist_ok=True)
    candidate = Path(tempfile.mkdtemp(prefix="ff7r2-candidate-", dir=build_root))
    output_utoc = candidate / f"{PACKAGE_NAME}.utoc"
    staged = project / STAGED_PLAYER
    staged_sha256 = _sha256(staged)
    packer_sha256 = _sha256(packer)
    deps_sha256 = _sha256(deps)
    oodle_sha256 = _sha256(oodle)

    try:
        command = [
            str(packer),
            "--game-dir", str(game_paks),
            "--content-path", str(content_root),
            "--engine-version", ENGINE_VERSION,
            "--output-path", str(output_utoc),
            "--compression-format", "Zlib",
            "--mount-point", MOUNT_POINT,
            "--game-dir-top-only",
        ]
        try:
            completed = runner(
                command,
                cwd=str(packer.parent),
                env=dict(env),
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise PackagingError("UnrealReZen timed out after 300 seconds") from error
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            if len(detail) > 800:
                detail = detail[-800:]
            raise PackagingError(
                f"UnrealReZen exited with {completed.returncode}"
                + (f": {detail}" if detail else "")
            )

        if _sha256(staged) != staged_sha256:
            raise PackagingError("Staged PlayerParameter changed while the package was being built")
        if _sha256(packer) != packer_sha256:
            raise PackagingError("UnrealReZen executable changed while the package was being built")
        if _sha256(deps) != deps_sha256:
            raise PackagingError("UnrealReZen dependency manifest changed while the package was being built")
        if _sha256(oodle) != oodle_sha256:
            raise PackagingError("Supplied Oodle DLL changed while the package was being built")

        outputs = [
            output_utoc,
            output_utoc.with_suffix(".ucas"),
            output_utoc.with_suffix(".pak"),
        ]
        missing_outputs = [path.name for path in outputs if not path.is_file() or path.stat().st_size == 0]
        if missing_outputs:
            raise PackagingError(
                "UnrealReZen did not produce the complete candidate: "
                + ", ".join(missing_outputs)
            )

        manifest = {
            "schema": 1,
            "game": "ff7r2",
            "kind": "isolated-package-candidate",
            "acceptedInGame": False,
            "installed": False,
            "input": {
                "path": STAGED_PLAYER.as_posix(),
                "sha256": staged_sha256,
            },
            "tooling": {
                "unrealReZen": {
                    "sha256": packer_sha256,
                    "depsSha256": deps_sha256,
                    "requiredCUE4Parse": CUE4PARSE_VERSION,
                },
                "oodle": {
                    "sha256": oodle_sha256,
                    "path": str(oodle),
                    "requiredName": OODLE_NAME,
                    "alreadyInToolDirectory": True,
                },
                "engine": ENGINE_VERSION,
                "compression": "Zlib",
                "mountPoint": MOUNT_POINT,
                "gameDirTopOnly": True,
                "dependencyDownloadInvokedByLexeditor": False,
            },
            "outputs": [
                {"file": path.name, "sha256": _sha256(path), "bytes": path.stat().st_size}
                for path in outputs
            ],
        }
        manifest_path = candidate / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        return {
            "candidateDirectory": str(candidate),
            "manifest": str(manifest_path),
            "outputs": [str(path) for path in outputs],
            "installed": False,
            "acceptedInGame": False,
        }
    except Exception:
        shutil.rmtree(candidate, ignore_errors=True)
        raise
