"""Pinned repak integration for FF7 Remake PAK indexing, extraction and packing."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile

from runtime_bootstrap import user_data_dir


REPAK_VERSION = "0.2.3"
REPAK_TAG = f"v{REPAK_VERSION}"
# Public FF7R asset archive key, documented by the FF7R Data Editor project.
FF7R_AES_KEY = "0x23989837645C9D28BA58072B2076E895B853A7C9E1C5591B814C4FD2A2D7B782"
RELEASE_BASE = f"https://github.com/trumank/repak/releases/download/{REPAK_TAG}"
DOWNLOADS = {
    "win32": (
        f"{RELEASE_BASE}/repak_cli-x86_64-pc-windows-msvc.zip",
        "6720d602144d75df477a99d5bedb6ea780997546afc335901d4937cafeaa73fa",
        "zip",
        "repak.exe",
    ),
    "linux": (
        f"{RELEASE_BASE}/repak_cli-x86_64-unknown-linux-gnu.tar.xz",
        "933bdb8e26f34e8fd70ea50201efca39df041de58aa83b1cd6eb83da124a2046",
        "tar.xz",
        "repak",
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


def helper_status() -> dict:
    target = repak_path()
    installed = target.is_file()
    return {
        "runtime": "repak",
        "installed": installed,
        "version": REPAK_TAG if installed else "",
        "pinned": REPAK_TAG,
        "path": str(target),
        "message": "" if installed else f"Install pinned repak {REPAK_TAG} to read and build FF7R PAK archives.",
    }


def _download_spec():
    key = "win32" if os.name == "nt" else sys.platform
    if key not in DOWNLOADS:
        raise RuntimeError(f"No pinned repak binary is configured for {sys.platform}")
    return DOWNLOADS[key]


def helper_install() -> dict:
    url, expected_sha, archive_kind, member_name = _download_spec()
    root = helper_root()
    root.mkdir(parents=True, exist_ok=True)
    target = repak_path()
    if target.is_file():
        return helper_status()
    with tempfile.TemporaryDirectory(prefix="lexeditor-repak-") as temp_name:
        archive = Path(temp_name) / ("repak.zip" if archive_kind == "zip" else "repak.tar.xz")
        with urllib.request.urlopen(url, timeout=60) as response, archive.open("wb") as output:
            shutil.copyfileobj(response, output)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        if digest != expected_sha:
            raise RuntimeError(f"repak download SHA-256 mismatch: expected {expected_sha}, got {digest}")
        extracted = Path(temp_name) / Path(member_name).name
        if archive_kind == "zip":
            with zipfile.ZipFile(archive) as package:
                candidates = [name for name in package.namelist() if Path(name).name == Path(member_name).name]
                if len(candidates) != 1:
                    raise RuntimeError("Pinned repak archive does not contain exactly one executable")
                extracted.write_bytes(package.read(candidates[0]))
        else:
            with tarfile.open(archive, "r:xz") as package:
                members = [member for member in package.getmembers()
                           if member.isfile() and Path(member.name).name == Path(member_name).name]
                if len(members) != 1:
                    raise RuntimeError("Pinned repak archive does not contain exactly one executable")
                source = package.extractfile(members[0])
                if source is None:
                    raise RuntimeError("Could not read repak executable from archive")
                extracted.write_bytes(source.read())
        if os.name != "nt":
            extracted.chmod(0o755)
        temporary = target.with_suffix(target.suffix + ".tmp")
        shutil.copy2(extracted, temporary)
        if os.name != "nt":
            temporary.chmod(0o755)
        temporary.replace(target)
    return helper_status()


def _command(*args: str, binary: bool = False) -> subprocess.CompletedProcess:
    executable = repak_path()
    if not executable.is_file():
        raise RuntimeError(helper_status()["message"])
    command = [str(executable), "--aes-key", FF7R_AES_KEY, *map(str, args)]
    return subprocess.run(
        command, check=True, capture_output=True,
        text=not binary, timeout=180,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def list_pak(pak: Path) -> list[str]:
    result = _command("list", str(Path(pak)))
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def get_file(pak: Path, internal_path: str) -> bytes:
    result = _command("get", str(Path(pak)), internal_path, binary=True)
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
    command = [str(repak_path()), "pack", "--quiet"]
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
