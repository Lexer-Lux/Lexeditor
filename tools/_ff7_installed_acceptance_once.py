"""One-shot patch for FF7 installed-data acceptance evidence."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_one(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one marker, found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


kernel = ROOT / "games/ff7/kernel.py"
replace_one(
    kernel,
    "        self.trailer = self.original[offset:]\n",
    "        self.trailer = self.original[offset:]\n"
    "        self.original_sections = tuple(bytes(section) for section in self.sections)\n"
    "        self.original_file_types = tuple(self.file_types)\n"
    "        self.original_trailer = self.trailer\n",
)
replace_one(
    kernel,
    "    def to_bytes(self) -> bytes:\n        output = bytearray()\n",
    "    def to_bytes(self) -> bytes:\n"
    "        # A no-op save must preserve the installed container byte-for-byte.\n"
    "        # Recompress only after modeled content actually changes; compressor\n"
    "        # provenance/header differences are otherwise meaningless churn.\n"
    "        if (tuple(self.file_types) == self.original_file_types\n"
    "                and self.trailer == self.original_trailer\n"
    "                and all(bytes(current) == original for current, original in zip(self.sections, self.original_sections))):\n"
    "            return self.original\n"
    "        output = bytearray()\n",
)

installed = ROOT / "tools/verify_ff7_installed.py"
installed.write_text(r'''"""Read installed FF7 data and prove a byte-exact disposable no-op round trip.

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
''', encoding="utf-8")

contract_test = ROOT / "tools/verify_ff7_installed_contract.py"
contract_test.write_text(r'''"""Asset-free regression for the FF7 installed acceptance checker."""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from games.ff7 import datasets, extended
from verify_ff7_completion import field_fixture, lgp_fixture, world_fixture
from verify_ff7_datasets import PATHS, write_kernel
from verify_ff7_extended import exe_fixture, scene_fixture, text_fixture
from verify_ff7_installed import EXPECTED_DATASETS, EXPECTED_FAMILY_DATASETS, check_installation, declared_family_datasets


class InstalledAcceptanceContractTests(unittest.TestCase):
    def test_backend_surface_matches_independent_38_dataset_contract(self):
        declared = declared_family_datasets()
        self.assertEqual(set(declared), set(EXPECTED_FAMILY_DATASETS))
        for family, expected in EXPECTED_FAMILY_DATASETS.items():
            self.assertEqual(set(declared[family]), set(expected), family)
        flattened = [key for rows in declared.values() for key in rows]
        self.assertEqual(len(flattened), 38)
        self.assertEqual(len(set(flattened)), 38)
        self.assertEqual(set(flattened), set(EXPECTED_DATASETS))

    def test_kernel_true_noop_preserves_noncanonical_gzip_header_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "KERNEL.BIN"
            write_kernel(path)
            raw = bytearray(path.read_bytes())
            # GZIP OS byte in section 1. It is not covered by the stream CRC and
            # deliberately differs from Python's own compressor provenance.
            raw[15] = (raw[15] + 1) & 0xFF
            path.write_bytes(raw)
            self.assertEqual(datasets.Kernel(path).to_bytes(), bytes(raw))

    def test_full_synthetic_install_produces_self_proving_acceptance_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            game = Path(temporary) / "game"
            write_kernel(game / PATHS[0])
            fixtures = {
                Path("data/battle/scene.bin"): scene_fixture(),
                Path("data/lang-en/kernel/kernel2.bin"): text_fixture(),
                Path("ff7_en.exe"): exe_fixture(),
                Path("data/field/flevel.lgp"): lgp_fixture([("field1", field_fixture())]),
                Path("data/wm/world_us.lgp"): lgp_fixture([("enc_w.bin", world_fixture())]),
            }
            for relative, raw in fixtures.items():
                target = game / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
            executable = fixtures[Path("ff7_en.exe")]
            identity = hashlib.sha1(executable).hexdigest().upper()
            with patch.dict(extended.EXE_PROFILES, {identity: 0x400}):
                report = check_installation(game)
            self.assertTrue(report["passed"], report["errors"])
            self.assertEqual(report["datasetCoverage"]["exercised"], 38)
            self.assertEqual(set(report["datasets"]), set(EXPECTED_DATASETS))
            self.assertEqual({entry["family"] for entry in report["rewrittenFiles"]}, set(EXPECTED_FAMILY_DATASETS))
            self.assertEqual(len(report["rewrittenFiles"]), 6)
            self.assertTrue(report["rewriteCoverage"]["allDisposable"])
            self.assertTrue(report["rewriteCoverage"]["allByteExactNoOps"])
            self.assertTrue(report["installedFilesUnchanged"])
            for entry in report["rewrittenFiles"]:
                self.assertEqual(entry["sourceSha256"], entry["projectSha256"])
                self.assertEqual(entry["sourceBytes"], entry["projectBytes"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
''', encoding="utf-8")

workflow = ROOT / ".github/workflows/ff7-data-regressions.yml"
replace_one(
    workflow,
    "          python tools/verify_ff7_completion.py\n          python tools/verify_ff7_edition_parity.py\n",
    "          python tools/verify_ff7_completion.py\n          python tools/verify_ff7_installed_contract.py\n          python tools/verify_ff7_edition_parity.py\n",
)

cmd = ROOT / "tools/FF7-checks.cmd"
replace_one(
    cmd,
    "echo FF7 installed-data checks. Only disposable project files are written.\n",
    "echo FF7 installed-data checks: 38/38 dataset coverage and byte-exact disposable no-op project copies.\n",
)
