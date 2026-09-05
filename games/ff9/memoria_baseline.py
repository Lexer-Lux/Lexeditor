"""Prepare a verified FF9 data baseline from Memoria's official release."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import threading
import urllib.request

from . import paths


RELEASE = "v2025.07.04"
SOURCE = f"https://github.com/Albeoris/Memoria/tree/{RELEASE}/Memoria.Patcher/StreamingAssets/Data"
RAW_ROOT = f"https://raw.githubusercontent.com/Albeoris/Memoria/{RELEASE}/Memoria.Patcher/StreamingAssets/Data"
FILES = {
    "Battle/Actions.csv": "d0d93ae1e0ae42daa295b5b4cf9cd9c00d495e64305a79da5b0dfcb94133742e",
    "Characters/BaseStats.csv": "02314fae328e63ad5aa716a0ea6593d88441ee79d12807bec44373de23f6506e",
    "Characters/Abilities/AbilityGems.csv": "8ac6a22345dcc49355349deb296411b736b13637df5726a1e042b733893b744a",
    "Items/Armors.csv": "216c21b16648c8bc51b8d76b5cda64e8434647f02b6c786bc2a0b20281a8b771",
    "Items/ItemEffects.csv": "9753fa025443ce2e8c8cf59733cad98c7023ef902949e299b1a3fa9d6cdce7b4",
    "Items/Items.csv": "966fee1bc4986ec94c2b05bf1e5299c9fc3497df4377dc002cd58bac96f9076f",
    "Items/ShopItems.csv": "589f12ccc6b2ee8a606f998dc068f945100c0a1928ee016d73b6b9b9e9897906",
    "Items/Synthesis.csv": "1cd6d012696685ae5d40ff788b8ad64e2fb814f930788b80a7aa81c7d9f3a8a0",
    "Items/Weapons.csv": "830e66a6ced06b92d22b487d4449ed5b873b712a21f83543202e7273f7b70527",
}
MAX_FILE_BYTES = 2 * 1024 * 1024
_lock = threading.Lock()
_last: dict | None = None


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _download(relative: str) -> bytes:
    request = urllib.request.Request(
        f"{RAW_ROOT}/{relative}", headers={"User-Agent": "Lexeditor/1.0"},
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        data = response.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise RuntimeError(f"Memoria baseline file is unexpectedly large: {relative}")
    return data


def ensure(root: Path | None = None, downloader=_download, force: bool = False) -> dict:
    """Download missing or invalid pinned files into Lexeditor's private cache."""
    global _last
    baseline = Path(root or paths.DATA_ROOT) / "StreamingAssets" / "Data"
    with _lock:
        if root is None and _last is not None and not force:
            return _last
        prepared, problems = 0, []
        for relative, expected in FILES.items():
            target = baseline / Path(relative)
            try:
                current = target.read_bytes() if target.is_file() else b""
                if current and _hash(current) == expected:
                    prepared += 1
                    continue
                data = downloader(relative)
                if _hash(data) != expected:
                    raise RuntimeError(f"Official Memoria baseline checksum failed: {relative}")
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_name(target.name + ".lexeditor.tmp")
                temporary.write_bytes(data)
                temporary.replace(target)
                prepared += 1
            except Exception as error:
                problems.append(str(error))
                break
        manifest = {
            "release": RELEASE, "source": SOURCE, "prepared": prepared,
            "expected": len(FILES), "ready": prepared == len(FILES), "problems": problems,
        }
        if prepared:
            baseline.mkdir(parents=True, exist_ok=True)
            manifest_path = baseline.parent / "memoria-baseline.json"
            temporary = manifest_path.with_name(manifest_path.name + ".tmp")
            temporary.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            temporary.replace(manifest_path)
        if root is None:
            _last = manifest
        return manifest
