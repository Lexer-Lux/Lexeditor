"""Read installed FF7 data and prove a byte-exact disposable no-op round trip.

No deployment, game launch, installed-file writes, or automatic uploads.
Native gameplay and visual/audio judgement remain separate acceptance steps.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from games.ff7 import datasets, extended
from games.ff7.kernel import resolve_kernel


# Deliberately independent of the backend declarations below. If the editor's
# declared surface grows, shrinks, duplicates or moves a dataset between source
# families, installed acceptance fails until this contract is reviewed too.
EXPECTED_FAMILY_DATASETS = {
    "kernel": (
        "commands", "playerAttacks", "items", "weapons", "armor", "accessories", "materia",
        "characters", "characterNames", "growthCurves", "growthBonuses", "characterAI",
        "magicOrder", "initialState", "initialInventory", "initialMateria", "stolenMateria",
    ),
    "scene": ("enemies", "enemyAI", "formationAI", "encounters", "enemyAttacks"),
    "text": ("texts",),
    "shop": (
        "shops", "prices", "recruits", "defaultNames", "limitBreaks", "materiaEquipEffects",
        "exeText", "itemSortOrder", "materiaPriority", "audioMixing", "apMultiplier",
    ),
    "field": ("fieldEncounters",),
    "world": ("worldEncounters", "yuffieEncounters", "chocoboRatings"),
}
EXPECTED_DATASETS = tuple(key for keys in EXPECTED_FAMILY_DATASETS.values() for key in keys)
if len(EXPECTED_DATASETS) != 38 or len(set(EXPECTED_DATASETS)) != 38:
    raise RuntimeError("FF7 installed acceptance contract must contain exactly 38 unique datasets")


def sha256(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest().upper()


def declared_family_datasets() -> dict[str, tuple[str, ...]]:
    return {
        "kernel": tuple(datasets.CATEGORIES),
        **{family: tuple(info["categories"]) for family, info in extended.FAMILIES.items()},
    }


def _record_contract(report: dict) -> None:
    declared = declared_family_datasets()
    expected_families = set(EXPECTED_FAMILY_DATASETS)
    declared_families = set(declared)
    family_rows = {}
    passed = expected_families == declared_families
    for family in sorted(expected_families | declared_families):
        expected = set(EXPECTED_FAMILY_DATASETS.get(family, ()))
        actual = set(declared.get(family, ()))
        row = {
            "expected": list(EXPECTED_FAMILY_DATASETS.get(family, ())),
            "declared": list(declared.get(family, ())),
            "missing": sorted(expected - actual),
            "unexpected": sorted(actual - expected),
        }
        row["passed"] = not row["missing"] and not row["unexpected"]
        family_rows[family] = row
        passed = passed and row["passed"]
    flattened = [key for keys in declared.values() for key in keys]
    counts = Counter(flattened)
    duplicates = sorted(key for key, count in counts.items() if count > 1)
    passed = passed and len(flattened) == 38 and len(counts) == 38 and not duplicates
    report["datasetContract"] = {
        "expectedCount": 38,
        "declaredCount": len(flattened),
        "uniqueDeclaredCount": len(counts),
        "missingFamilies": sorted(expected_families - declared_families),
        "unexpectedFamilies": sorted(declared_families - expected_families),
        "duplicateDatasets": duplicates,
        "families": family_rows,
        "passed": passed,
    }
    if not passed:
        report["errors"]["datasetContract"] = "Backend dataset declarations differ from the reviewed 38-dataset installed acceptance contract."


def _source_entry(path: Path) -> dict:
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def _record_rewrite(report: dict, family: str, source: Path, result: dict, project_root: Path, game_root: Path) -> None:
    source = source.resolve()
    project = Path(result["path"]).resolve()
    entry = {
        "family": family,
        "source": str(source),
        "project": str(project),
        "temporary": True,
        "projectIsDisposable": False,
        "byteExactNoOp": False,
    }
    try:
        if not project.is_file():
            raise ValueError("save returned a project path that does not exist")
        entry.update(
            sourceBytes=source.stat().st_size,
            projectBytes=project.stat().st_size,
            sourceSha256=sha256(source),
            projectSha256=sha256(project),
        )
        entry["projectIsDisposable"] = (
            project != source
            and project.is_relative_to(project_root.resolve())
            and not project.is_relative_to(game_root.resolve())
        )
        entry["byteExactNoOp"] = (
            entry["sourceBytes"] == entry["projectBytes"]
            and entry["sourceSha256"] == entry["projectSha256"]
        )
        if not entry["projectIsDisposable"]:
            report["errors"][f"{family}ProjectPath"] = "No-op save did not resolve strictly inside the disposable project root."
        if not entry["byteExactNoOp"]:
            report["errors"][f"{family}NoOpBytes"] = "No-op project copy differs from the installed source bytes."
    except (OSError, ValueError) as error:
        report["errors"][f"{family}RewriteEvidence"] = str(error)
    report["rewrittenFiles"].append(entry)


def _record_dataset_readback(report: dict, key: str, expected_rows: list, actual_rows: list | None, family: str) -> None:
    if expected_rows != actual_rows:
        report["errors"][f"{key}Readback"] = f"{key}: disposable project readback differs"
        return
    report["datasets"][key] = {"family": family, "records": len(expected_rows), "readback": "passed"}


def check_installation(game: Path) -> dict:
    game = game.resolve()
    report = {
        "game": str(game),
        "datasets": {},
        "errors": {},
        "sourceFiles": {},
        "rewrittenFiles": [],
        "installedFilesUnchanged": False,
        "scope": "Read installed sources and write/reopen only disposable no-op project copies; not deployment or gameplay acceptance.",
    }
    _record_contract(report)

    sources: dict[str, Path] = {}
    try:
        sources["kernel"] = resolve_kernel(game)[0]
    except (OSError, ValueError) as error:
        report["errors"]["source:kernel"] = str(error)
    for family in extended.FAMILIES:
        try:
            sources[family] = extended.resolve_source(game, family)[0]
        except (OSError, ValueError) as error:
            report["errors"][f"source:{family}"] = str(error)

    before = {}
    for family, path in sources.items():
        try:
            entry = _source_entry(path)
            report["sourceFiles"][family] = entry
            before[path.resolve()] = entry["sha256"]
        except OSError as error:
            report["errors"][f"sourceHash:{family}"] = str(error)

    with tempfile.TemporaryDirectory(prefix="lexeditor-ff7-readback-") as temporary:
        project = Path(temporary).resolve() / "project"

        kernel = datasets.load_datasets(game, project)
        report["errors"].update(kernel["errors"])
        if kernel["records"]:
            try:
                result = datasets.save_datasets(game, project, kernel)
                if "kernel" in sources:
                    _record_rewrite(report, "kernel", sources["kernel"], result, project, game)
                restored = datasets.load_datasets(game, project)
                for key, value in restored["errors"].items():
                    report["errors"].setdefault(f"{key}ReadbackLoad", value)
                for key, rows in kernel["records"].items():
                    _record_dataset_readback(report, key, rows, restored["records"].get(key), "kernel")
            except Exception as error:
                report["errors"]["kernelSave"] = str(error)

        other = extended.load_extended(game, project)
        report["errors"].update(other["errors"])
        saved_families: dict[str, dict[str, list]] = {}
        for family, metadata in other["families"].items():
            records = {key: other["records"][key] for key in metadata["categories"] if key in other["records"]}
            if metadata.get("memberErrors"):
                report["errors"][family + "Members"] = metadata["memberErrors"]
            if not records:
                continue
            try:
                result = extended.save_extended(game, project, dict(metadata, family=family, records=records))
                saved_families[family] = records
                if family in sources:
                    _record_rewrite(report, family, sources[family], result, project, game)
            except Exception as error:
                report["errors"][family + "Save"] = str(error)

        # Reopen the completed disposable project once, rather than trusting only
        # the serializer's in-memory verification result.
        restored = extended.load_extended(game, project)
        for key, value in restored["errors"].items():
            report["errors"].setdefault(f"{key}ReadbackLoad", value)
        for family, records in saved_families.items():
            for key, rows in records.items():
                _record_dataset_readback(report, key, rows, restored["records"].get(key), family)

    expected = set(EXPECTED_DATASETS)
    exercised = set(report["datasets"])
    report["datasetCoverage"] = {
        "expected": 38,
        "exercised": len(exercised),
        "missing": sorted(expected - exercised),
        "unexpected": sorted(exercised - expected),
    }
    report["datasetCoverage"]["passed"] = (
        report["datasetCoverage"]["exercised"] == 38
        and not report["datasetCoverage"]["missing"]
        and not report["datasetCoverage"]["unexpected"]
    )
    if not report["datasetCoverage"]["passed"]:
        report["errors"]["datasetCoverage"] = (
            f"Expected 38/38 datasets; exercised {len(exercised)}. "
            f"Missing: {', '.join(report['datasetCoverage']['missing']) or 'none'}; "
            f"unexpected: {', '.join(report['datasetCoverage']['unexpected']) or 'none'}."
        )

    rewritten = {entry["family"] for entry in report["rewrittenFiles"]}
    expected_rewrites = set(EXPECTED_FAMILY_DATASETS)
    report["rewriteCoverage"] = {
        "expected": len(expected_rewrites),
        "rewritten": len(rewritten),
        "missing": sorted(expected_rewrites - rewritten),
        "unexpected": sorted(rewritten - expected_rewrites),
        "allDisposable": bool(report["rewrittenFiles"]) and all(entry["projectIsDisposable"] for entry in report["rewrittenFiles"]),
        "allByteExactNoOps": bool(report["rewrittenFiles"]) and all(entry["byteExactNoOp"] for entry in report["rewrittenFiles"]),
    }
    report["rewriteCoverage"]["passed"] = (
        rewritten == expected_rewrites
        and len(report["rewrittenFiles"]) == len(expected_rewrites)
        and report["rewriteCoverage"]["allDisposable"]
        and report["rewriteCoverage"]["allByteExactNoOps"]
    )
    if not report["rewriteCoverage"]["passed"]:
        report["errors"]["rewriteCoverage"] = "Every one of the six expected source families must produce one disposable byte-exact no-op project copy."

    report["installedFilesUnchanged"] = bool(before) and all(
        path.is_file() and sha256(path) == value for path, value in before.items()
    )
    if not report["installedFilesUnchanged"]:
        report["errors"]["sourceIntegrity"] = "An installed file changed during the check. No installed file was intentionally written."

    report["passed"] = (
        report["datasetContract"]["passed"]
        and report["datasetCoverage"]["passed"]
        and report["rewriteCoverage"]["passed"]
        and report["installedFilesUnchanged"]
        and not report["errors"]
    )
    return report


def discover() -> list[Path]:
    from games.ff7.plugin import PLUGIN as current
    from games.ff7_2013.plugin import PLUGIN as legacy

    roots = []
    saved = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Lexeditor/game-installations.json"
    try:
        games = json.loads(saved.read_text(encoding="utf-8")).get("games", {})
        roots += [Path(games[key]["root"]) for key in ("ff7", "ff7-2013") if games.get(key, {}).get("root")]
    except (OSError, ValueError, TypeError):
        pass
    for plugin in (current, legacy):
        spec = plugin.installation
        if os.environ.get(spec.root_env):
            roots.append(Path(os.environ[spec.root_env]))
        roots.extend(spec.default_roots)
    return sorted({root.resolve() for root in roots if root.is_dir()}, key=str)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", type=Path, action="append", help="Installed game root; repeat for both editions. Otherwise use saved/default locations.")
    parser.add_argument("--report", type=Path, help="JSON report outside game directories.")
    args = parser.parse_args()
    roots = args.game or discover()
    if not roots:
        parser.error('No FF7 installation found. Supply --game "path to the installed game".')
    target = args.report or Path(tempfile.gettempdir()) / ("Lexeditor-ff7-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + ".json")
    if any(target.resolve().is_relative_to(root.resolve()) for root in roots):
        parser.error("The report must be outside all installed game directories.")
    reports = [check_installation(root) for root in roots]
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=target.name + ".", suffix=".tmp", mode="w", encoding="utf-8", delete=False) as stream:
        temp = Path(stream.name)
        json.dump(reports, stream, indent=2, ensure_ascii=False)
    try:
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)
    for report in reports:
        coverage = report["datasetCoverage"]
        rewrites = report["rewriteCoverage"]
        print(
            f"{report['game']}: {coverage['exercised']}/38 datasets; "
            f"{rewrites['rewritten']}/6 no-op project copies; "
            f"byte-exact: {rewrites['allByteExactNoOps']}; "
            f"sources unchanged: {report['installedFilesUnchanged']}; "
            f"{len(report['errors'])} problems"
        )
    print("Report:", target)
    return 0 if all(report["passed"] for report in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
