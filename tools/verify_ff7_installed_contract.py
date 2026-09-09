"""Asset-free regression for the FF7 installed acceptance checker."""
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
