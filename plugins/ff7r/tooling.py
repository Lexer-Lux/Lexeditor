"""Pinned repak integration for FF7 Remake PAK indexing, extraction and packing."""

from __future__ import annotations

import hashlib
import os
import json
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile

from functools import partial
from runtime_bootstrap import user_data_dir
from upstream_fetch import fetch_json


REPAK_VERSION = "0.2.3"
REPAK_TAG = f"v{REPAK_VERSION}"
REPAK_SOURCE = "https://github.com/trumank/repak"
REPAK_RELEASE = f"{REPAK_SOURCE}/releases/tag/{REPAK_TAG}"
LATEST_RELEASE_API = "https://api.github.com/repos/trumank/repak/releases/latest"
FF7R_MOUNT_POINT = "../../../"
# Public FF7R asset archive key, documented by the FF7R Data Editor project.
FF7R_AES_KEY = "0x23989837645C9D28BA58072B2076E895B853A7C9E1C5591B814C4FD2A2D7B782"

PLUGIN_ROOT = Path(__file__).resolve().parent
BUNDLE_ROOT = PLUGIN_ROOT / "runtime" / "repak" / REPAK_TAG
BUNDLES = {
    "win32": (
        BUNDLE_ROOT / "repak_cli-x86_64-pc-windows-msvc.zip",
        "6720d602144d75df477a99d5bedb6ea780997546afc335901d4937cafeaa73fa",
        "zip",
        "repak.exe",
        "fcd538e5994b9bb833622d425ae346f4e0692f02d4b0025114a559f9b6286022",
    ),
    "linux": (
        BUNDLE_ROOT / "repak_cli-x86_64-unknown-linux-gnu.tar.xz",
        "933bdb8e26f34e8fd70ea50201efca39df041de58aa83b1cd6eb83da124a2046",
        "tar.xz",
        "repak",
        "fce30661c951ce56fd2507a44a1e03637e3ea06a1b7cc8035bd62c0b37dd9457",
    ),
}

def helper_root() -> Path:
    return user_data_dir() / "tools" / "repak" / REPAK_TAG


def repak_path() -> Path:
    override = os.environ.get("LEXEDITOR_REPAK")
    if override:
        return Path(override).expanduser().resolve()
    name = "repak.exe" if os.name == "nt" else "repak"
    return helper_root() / name


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _bundle_spec():
    key = "win32" if os.name == "nt" else sys.platform
    if key not in BUNDLES:
        raise RuntimeError(f"No bundled repak binary is configured for {sys.platform}")
    return BUNDLES[key]


def helper_status() -> dict:
    target = repak_path()
    override = bool(os.environ.get("LEXEDITOR_REPAK"))
    try:
        archive, archive_sha, _kind, _member, executable_sha = _bundle_spec()
        archive_present = archive.is_file()
        archive_actual = _sha256_file(archive) if archive_present else ""
        package_integrity = "verified" if archive_present and archive_actual == archive_sha else (
            "mismatch" if archive_present else "missing"
        )
    except RuntimeError as error:
        archive = Path()
        archive_sha = executable_sha = archive_actual = ""
        package_integrity = "unsupported"
        bundle_error = str(error)
    else:
        bundle_error = ""

    target_exists = target.is_file()
    target_actual = _sha256_file(target) if target_exists and not override else ""
    if override:
        installed = target_exists
        integrity = "external" if target_exists else "missing"
    else:
        installed = target_exists and bool(executable_sha) and target_actual == executable_sha
        integrity = "verified" if installed else ("mismatch" if target_exists else "missing")

    if override and not target_exists:
        message = f"LEXEDITOR_REPAK points to a missing helper: {target}"
    elif not override and package_integrity != "verified":
        message = (
            f"Bundled repak {REPAK_TAG} package is {package_integrity}. "
            "Repair or reinstall Lexeditor before installing the helper."
        )
        if bundle_error:
            message = bundle_error
    elif not installed:
        message = (
            f"Install bundled repak {REPAK_TAG} to read and build FF7R PAK archives."
            if not target_exists else
            f"Installed repak {REPAK_TAG} failed SHA-256 verification; use Install/Repair."
        )
    else:
        message = (
            f"Using explicit external repak at {target}."
            if override else
            f"Pinned repak {REPAK_TAG} verified from the bundled release."
        )

    return {
        "runtime": "repak",
        "installed": installed,
        "version": REPAK_TAG if installed and not override else ("external" if installed else ""),
        "pinned": REPAK_TAG,
        "packageVersion": REPAK_TAG,
        "path": str(target),
        "source": REPAK_SOURCE,
        "releaseNotes": REPAK_RELEASE,
        "autoUpdate": False,
        "integrity": integrity,
        "packageIntegrity": package_integrity,
        "packagePath": str(archive) if archive else "",
        "expectedExecutableSha256": executable_sha,
        "actualExecutableSha256": target_actual,
        "message": message,
    }


def _version_tuple(value: str) -> tuple[int, int, int] | None:
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", str(value).strip())
    return tuple(map(int, match.groups())) if match else None


_fetch_json = partial(
    fetch_json,
    user_agent="Lexeditor-FF7R/1",
    size_error="repak release metadata is too large",
)


def upstream_release(fetch_json=None) -> dict:
    """Report upstream availability without changing the pinned helper."""
    base = {
        "runtime": "repak",
        "pinned": REPAK_TAG,
        "packageVersion": REPAK_TAG,
        "source": REPAK_SOURCE,
        "releaseNotes": REPAK_RELEASE,
        "autoUpdate": False,
    }
    try:
        payload = (fetch_json or _fetch_json)(LATEST_RELEASE_API)
        latest = str(payload.get("tag_name", ""))
        parsed = _version_tuple(latest)
        pinned = _version_tuple(REPAK_TAG)
        if parsed is None or pinned is None or payload.get("draft") or payload.get("prerelease"):
            raise RuntimeError("Upstream did not return a stable repak release")
        return {
            **base,
            "latest": latest,
            "published": str(payload.get("published_at", "")),
            "releaseNotes": str(payload.get("html_url") or f"{REPAK_SOURCE}/releases/tag/{latest}"),
            "behind": parsed > pinned,
        }
    except Exception as error:
        return {**base, "error": str(error), "behind": False}


def helper_install() -> dict:
    target = repak_path()
    if os.environ.get("LEXEDITOR_REPAK"):
        status = helper_status()
        if status["installed"]:
            return status
        raise RuntimeError(
            "LEXEDITOR_REPAK is an explicit external helper override; "
            "Install/Repair will not create or overwrite that path."
        )

    archive, expected_archive_sha, archive_kind, member_name, expected_executable_sha = _bundle_spec()
    if not archive.is_file():
        raise RuntimeError(f"Bundled repak archive is missing: {archive}")
    actual_archive_sha = _sha256_file(archive)
    if actual_archive_sha != expected_archive_sha:
        raise RuntimeError(
            "Bundled repak archive SHA-256 mismatch: "
            f"expected {expected_archive_sha}, got {actual_archive_sha}"
        )

    root = helper_root()
    root.mkdir(parents=True, exist_ok=True)
    if target.is_file() and _sha256_file(target) == expected_executable_sha:
        return helper_status()

    with tempfile.TemporaryDirectory(prefix="lexeditor-repak-") as temp_name:
        extracted = Path(temp_name) / Path(member_name).name
        if archive_kind == "zip":
            with zipfile.ZipFile(archive) as package:
                candidates = [name for name in package.namelist()
                              if Path(name).name == Path(member_name).name]
                if len(candidates) != 1:
                    raise RuntimeError("Bundled repak archive does not contain exactly one executable")
                extracted.write_bytes(package.read(candidates[0]))
        else:
            with tarfile.open(archive, "r:xz") as package:
                members = [member for member in package.getmembers()
                           if member.isfile() and Path(member.name).name == Path(member_name).name]
                if len(members) != 1:
                    raise RuntimeError("Bundled repak archive does not contain exactly one executable")
                source = package.extractfile(members[0])
                if source is None:
                    raise RuntimeError("Could not read repak executable from bundled archive")
                extracted.write_bytes(source.read())

        actual_executable_sha = _sha256_file(extracted)
        if actual_executable_sha != expected_executable_sha:
            raise RuntimeError(
                "Bundled repak executable SHA-256 mismatch: "
                f"expected {expected_executable_sha}, got {actual_executable_sha}"
            )
        if os.name != "nt":
            extracted.chmod(0o755)
        temporary = target.with_suffix(target.suffix + ".tmp")
        shutil.copy2(extracted, temporary)
        if os.name != "nt":
            temporary.chmod(0o755)
        temporary.replace(target)

    status = helper_status()
    if not status["installed"]:
        raise RuntimeError(status["message"])
    return status

def _command(*args: str, binary: bool = False) -> subprocess.CompletedProcess:
    status = helper_status()
    if not status["installed"]:
        raise RuntimeError(status["message"])
    executable = repak_path()
    command = [str(executable), "--aes-key", FF7R_AES_KEY, *map(str, args)]
    return subprocess.run(
        command, check=True, capture_output=True,
        text=not binary, timeout=180,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def list_pak(pak: Path) -> list[str]:
    result = _command("list", "--strip-prefix", FF7R_MOUNT_POINT, str(Path(pak)))
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def get_file(pak: Path, internal_path: str) -> bytes:
    # repak cannot read this game's legacy Custom/Oodle entries correctly, so
    # the direct reader is authoritative. repak's default oodle feature can
    # fetch an Oodle library beside itself when one is missing; Lexeditor must
    # never allow a helper to silently download a dependency. The compatibility
    # fallback therefore runs only when an Oodle library is already explicit.
    from .pak_reader import PakError, read_file, repak_oodle_library

    try:
        return read_file(Path(pak), internal_path)
    except PakError as error:
        if repak_oodle_library() is None:
            raise RuntimeError(
                "FF7R direct PAK reading failed and the repak fallback is disabled because "
                "no explicit Oodle library is present beside repak. Lexeditor will not let "
                "repak download Oodle automatically."
            ) from error
        result = _command("get", "--strip-prefix", FF7R_MOUNT_POINT,
                          str(Path(pak)), internal_path, binary=True)
        return bytes(result.stdout)


def pak_info(pak: Path) -> dict:
    result = _command("info", str(Path(pak)))
    values = {}
    for line in result.stdout.splitlines():
        key, separator, value = line.partition(":")
        if separator:
            values[key.strip()] = value.strip()
    return values


def pack_directory(source: Path, output: Path, *, version: str = "") -> Path:
    source = Path(source).resolve()
    output = Path(output).resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"FF7R project content directory does not exist: {source}")
    output.parent.mkdir(parents=True, exist_ok=True)
    status = helper_status()
    if not status["installed"]:
        raise RuntimeError(status["message"])
    command = [
        str(repak_path()), "pack", "--quiet",
        "--mount-point", FF7R_MOUNT_POINT,
    ]
    if version:
        command.extend(["--version", version])
    command.extend([str(source), str(output)])
    subprocess.run(
        command, check=True, capture_output=True, text=True, timeout=300,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if not output.is_file() or output.stat().st_size <= 0:
        raise RuntimeError("repak did not create the requested FF7R mod PAK")
    return output
