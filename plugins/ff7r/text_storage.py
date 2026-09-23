"""Safe project-overlay storage for FF7R text-resource packages."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .archive import extract_pair
from .textresource import TextResourcePackage, sha256_bytes


def _project_target(project_root: Path, asset: str, suffix: str) -> Path:
    content = (Path(project_root).resolve() / "content").resolve()
    target = (content / (asset + suffix)).resolve()
    if target != content and content not in target.parents:
        raise ValueError(f"Unsafe FF7R project path: {asset}")
    return target


def load_text_package(game_root: Path, data_root: Path, project_root: Path,
                      index: dict, asset: str, *, vanilla: bool = False
                      ) -> tuple[TextResourcePackage, str, str, bool]:
    source_uasset, source_uexp = extract_pair(
        game_root, data_root, index, asset, collection="textAssets")
    source_uasset_sha = sha256_bytes(source_uasset.read_bytes())
    source_uexp_sha = sha256_bytes(source_uexp.read_bytes())
    project_uasset = _project_target(project_root, asset, ".uasset")
    project_uexp = _project_target(project_root, asset, ".uexp")
    using_project = not vanilla and project_uasset.is_file() and project_uexp.is_file()
    package = TextResourcePackage(
        project_uasset if using_project else source_uasset,
        project_uexp if using_project else source_uexp,
        asset=asset,
    )
    return package, source_uasset_sha, source_uexp_sha, using_project


def save_text_edits(game_root: Path, data_root: Path, project_root: Path,
                    index: dict, asset: str, *, source_uasset_sha256: str,
                    source_uexp_sha256: str, active_uasset_sha256: str,
                    active_uexp_sha256: str, edits: list[dict[str, Any]]) -> dict:
    package, actual_source_uasset_sha, actual_source_uexp_sha, _using_project = load_text_package(
        game_root, data_root, project_root, index, asset, vanilla=False)
    if actual_source_uasset_sha != source_uasset_sha256 or actual_source_uexp_sha != source_uexp_sha256:
        raise RuntimeError("Installed FF7R text source changed; reload this text resource before saving")
    if sha256_bytes(package.uasset_bytes) != active_uasset_sha256 or sha256_bytes(package.uexp_bytes) != active_uexp_sha256:
        raise RuntimeError("The FF7R project text resource changed on disk; reload before saving")

    package.apply_edits(edits)
    target_uasset = _project_target(project_root, asset, ".uasset")
    target_uexp = _project_target(project_root, asset, ".uexp")
    package.write_pair(target_uasset, target_uexp)
    verified = TextResourcePackage(target_uasset, target_uexp, asset=asset)
    if (sha256_bytes(verified.uasset_bytes) != sha256_bytes(package.uasset_bytes)
            or sha256_bytes(verified.uexp_bytes) != sha256_bytes(package.uexp_bytes)):
        raise RuntimeError("FF7R text-resource write failed binary readback verification")
    return {
        "asset": asset,
        "path": str(target_uexp),
        "saved": len(edits),
        "activeUassetSha256": sha256_bytes(verified.uasset_bytes),
        "activeUexpSha256": sha256_bytes(verified.uexp_bytes),
        "usingProject": True,
    }


def resident_text_map(game_root: Path, data_root: Path, project_root: Path,
                      index: dict, language: str = "US") -> dict[str, str]:
    language = language.upper()
    candidates = [row for row in index.get("textAssets", [])
                  if str(row.get("language", "")).upper() == language
                  and str(row.get("name", "")).casefold() == "resident_txtres"]
    if not candidates:
        return {}
    package, _source_uasset_sha, _source_uexp_sha, _using_project = load_text_package(
        game_root, data_root, project_root, index, candidates[0]["asset"], vanilla=False)
    return package.text_map()
