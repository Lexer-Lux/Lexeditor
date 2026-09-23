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


def _candidate_manifests(project: Path | None) -> list[Path]:
    if project is None:
        return []
    build = project / "build"
    if not build.is_dir():
        return []
    return sorted(build.glob("ff7r2-candidate-*/manifest.json"))


def status(project: Path | None, game: Path | None,
           environment: Mapping[str, str] | None = None) -> dict:
    """Return candidate-builder readiness without executing external software."""
    env = os.environ if environment is None else environment
    packer = _explicit_path(env, UNREALREZEN_ENV)
    oodle = _explicit_path(env, OODLE_ENV)
    staged = project / STAGED_PLAYER if project is not None else None
    paks = game / "End/Content/Paks" if game is not None else None

    packer_present = bool(packer and packer.is_file())
    oodle_present = bool(oodle and oodle.is_file())
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
    if not oodle_present:
        missing.append(f"explicit {OODLE_ENV} DLL")

    manifests = _candidate_manifests(project)
    return {
        "ready": not missing,
        "missing": missing,
        "packerExplicit": packer is not None,
        "packerPresent": packer_present,
        "packerPath": str(packer) if packer else "",
        "oodleExplicit": oodle is not None,
        "oodlePresent": oodle_present,
        "oodlePath": str(oodle) if oodle else "",
        "stagedPresent": staged_present,
        "gameArchivesPresent": archives_present,
        "candidateCount": len(manifests),
        "latestManifest": str(manifests[-1]) if manifests else "",
        "mode": "candidate-only",
        "installsGame": False,
        "downloadsDependencies": False,
    }


def _plan(project: Path | None, game: Path | None,
          environment: Mapping[str, str]) -> tuple[Path, Path, Path, Path]:
    state = status(project, game, environment)
    if not state["ready"]:
        raise PackagingError(
            "Package candidate is not ready: " + "; ".join(state["missing"])
        )
    assert project is not None and game is not None
    packer = Path(state["packerPath"]).resolve()
    oodle = Path(state["oodlePath"]).resolve()
    content_root = (project / "content/End/Content").resolve()
    paks = (game / "End/Content/Paks").resolve()
    return packer, oodle, content_root, paks


def build_candidate(project: Path | None, game: Path | None,
                    environment: Mapping[str, str] | None = None,
                    runner=subprocess.run) -> dict:
    """Build an isolated, never-installed IoStore candidate.

    UnrealReZen's FF7R2 fork loads CUE4Parse Oodle at startup even when package
    compression is Zlib.  Lexeditor therefore places the explicitly supplied
    DLL in an isolated working directory before the process starts.  Proxy
    variables are pointed at an unreachable loopback endpoint as defense in
    depth: an unexpected downloader path must fail rather than acquire Oodle.
    """
    env = dict(os.environ if environment is None else environment)
    packer, oodle, content_root, game_paks = _plan(project, game, env)
    assert project is not None

    build_root = project / "build"
    build_root.mkdir(parents=True, exist_ok=True)
    candidate = Path(tempfile.mkdtemp(prefix="ff7r2-candidate-", dir=build_root))
    output_utoc = candidate / f"{PACKAGE_NAME}.utoc"
    staged = project / STAGED_PLAYER

    try:
        with tempfile.TemporaryDirectory(prefix="lexeditor-ff7r2-packer-") as runtime_name:
            runtime = Path(runtime_name)
            runtime_oodle = runtime / OODLE_NAME
            shutil.copy2(oodle, runtime_oodle)
            expected_oodle = _sha256(runtime_oodle)

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
            process_env = dict(env)
            blocked_proxy = "http://127.0.0.1:9"
            process_env.update({
                "HTTP_PROXY": blocked_proxy,
                "HTTPS_PROXY": blocked_proxy,
                "ALL_PROXY": blocked_proxy,
                "NO_PROXY": "127.0.0.1,localhost",
            })
            completed = runner(
                command,
                cwd=str(runtime),
                env=process_env,
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
            if completed.returncode != 0:
                detail = (completed.stderr or completed.stdout or "").strip()
                if len(detail) > 800:
                    detail = detail[-800:]
                raise PackagingError(
                    f"UnrealReZen exited with {completed.returncode}"
                    + (f": {detail}" if detail else "")
                )
            if not runtime_oodle.is_file() or _sha256(runtime_oodle) != expected_oodle:
                raise PackagingError("UnrealReZen modified the supplied Oodle runtime copy")

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
                "sha256": _sha256(staged),
            },
            "tooling": {
                "unrealReZen": {"sha256": _sha256(packer)},
                "oodle": {"sha256": _sha256(oodle), "copiedAs": OODLE_NAME},
                "engine": ENGINE_VERSION,
                "compression": "Zlib",
                "mountPoint": MOUNT_POINT,
                "gameDirTopOnly": True,
                "networkFallbackBlocked": True,
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
