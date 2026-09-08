"""Safe project-overlay reads and writes for FF7 Remake DataObjects."""

from __future__ import annotations

from pathlib import Path
import shutil
from typing import Any

from .archive import extract_pair
from .dataobject import DataObjectPackage, sha256_bytes


def _project_target(project_root: Path, asset: str, suffix: str) -> Path:
    content = (Path(project_root).resolve() / "content").resolve()
    target = (content / (asset + suffix)).resolve()
    if target != content and content not in target.parents:
        raise ValueError(f"Unsafe FF7R project path: {asset}")
    return target


def load_package(game_root: Path, data_root: Path, project_root: Path,
                 index: dict, asset: str, *, vanilla: bool = False) -> tuple[DataObjectPackage, str, bool]:
    source_uasset, source_uexp = extract_pair(game_root, data_root, index, asset)
    source_sha = sha256_bytes(source_uexp.read_bytes())
    project_uasset = _project_target(project_root, asset, ".uasset")
    project_uexp = _project_target(project_root, asset, ".uexp")
    using_project = not vanilla and project_uasset.is_file() and project_uexp.is_file()
    package = DataObjectPackage(
        project_uasset if using_project else source_uasset,
        project_uexp if using_project else source_uexp,
        asset=asset,
    )
    return package, source_sha, using_project


def save_edits(game_root: Path, data_root: Path, project_root: Path,
               index: dict, asset: str, *, source_sha256: str,
               active_sha256: str, edits: list[dict[str, Any]]) -> dict:
    package, actual_source_sha, using_project = load_package(
        game_root, data_root, project_root, index, asset, vanilla=False)
    if actual_source_sha != source_sha256:
        raise RuntimeError("Installed FF7R source data changed; reload this DataObject before saving")
    if sha256_bytes(package.uexp_bytes) != active_sha256:
        raise RuntimeError("The FF7R project DataObject changed on disk; reload before saving")
    package.apply_edits(edits)

    source_uasset, _source_uexp = extract_pair(game_root, data_root, index, asset)
    target_uasset = _project_target(project_root, asset, ".uasset")
    target_uexp = _project_target(project_root, asset, ".uexp")
    target_uasset.parent.mkdir(parents=True, exist_ok=True)
    if not target_uasset.is_file():
        shutil.copy2(source_uasset, target_uasset)
    original_size = len(package.uexp_bytes)
    package.write_uexp(target_uexp)
    if target_uexp.stat().st_size != original_size:
        raise RuntimeError("FF7R project write changed the fixed-size .uexp payload")
    verified = DataObjectPackage(target_uasset, target_uexp, asset=asset)
    if sha256_bytes(verified.uexp_bytes) != sha256_bytes(package.uexp_bytes):
        raise RuntimeError("FF7R project write failed binary readback verification")
    return {
        "asset": asset,
        "path": str(target_uexp),
        "saved": len(edits),
        "activeSha256": sha256_bytes(verified.uexp_bytes),
        "usingProject": True,
    }
