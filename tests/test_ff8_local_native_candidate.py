"""Local candidate replacement/rollback without using a real game installation."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from games.ff8 import local_native_candidate as local


class LocalCandidateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="lexeditor-local-install-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.candidate, self.game = self.root / "candidate", self.root / "game"
        self.candidate.mkdir(); self.game.mkdir()
        (self.candidate / "AF3DN.P").write_bytes(b"candidate")
        (self.game / "AF3DN.P").write_bytes(b"original")
        (self.game / "FFNx.toml").write_bytes(b"settings")
        for name in ("ISSUE51_DERIVATIVE_SOURCE.patch", "SOURCE_INPUTS.sha256", "BUILD.txt", "LICENSE"):
            (self.candidate / name).write_text(name)
        self.digest = local.digest(self.candidate / "AF3DN.P")
        for target, value in (("verify_game_installation", self.game / "FF8_EN.exe"),
                              ("_pe_exports", (b"image", {})), ("_reject_unloadable_manifest", None)):
            started = patch.object(local.runtime_package, target, return_value=value)
            started.start(); self.addCleanup(started.stop)
        self.closed = patch.object(local, "_closed")
        self.closed.start(); self.addCleanup(self.closed.stop)

    def test_install_is_idempotent_and_rollback_preserves_new_settings(self):
        first = local.install(self.candidate, self.game, self.digest)
        second = local.install(self.candidate, self.game, self.digest)
        self.assertEqual(first, second)
        self.assertEqual((self.game / "FFNx.toml").read_bytes(), b"settings")
        self.assertEqual((self.candidate / "local-install/AF3DN.P").read_bytes(), b"original")
        (self.game / "FFNx.toml").write_bytes(b"new settings")
        self.assertEqual(local.rollback(self.candidate)["state"], "restored")
        self.assertEqual((self.game / "AF3DN.P").read_bytes(), b"original")
        self.assertEqual((self.game / "FFNx.toml").read_bytes(), b"new settings")
        local.install(self.candidate, self.game, self.digest)
        self.assertEqual(len(list((self.candidate / "local-install").iterdir())), 3)

    def test_running_game_blocks_writes(self):
        with patch.object(local, "_closed", side_effect=RuntimeError("running")):
            with self.assertRaisesRegex(RuntimeError, "running"):
                local.install(self.candidate, self.game, self.digest)
        self.assertEqual((self.game / "AF3DN.P").read_bytes(), b"original")
        self.assertFalse((self.candidate / "local-install").exists())

    def test_wrong_digest_and_external_replacement_are_not_overwritten(self):
        with self.assertRaises(ValueError):
            local.install(self.candidate, self.game, "0" * 64)
        local.install(self.candidate, self.game, self.digest)
        (self.game / "AF3DN.P").write_bytes(b"other mod")
        with self.assertRaisesRegex(RuntimeError, "changed"):
            local.rollback(self.candidate)
        self.assertEqual((self.game / "AF3DN.P").read_bytes(), b"other mod")

    def test_failed_receipt_write_restores_original_driver(self):
        write = local._write
        calls = 0
        def injected(path, data):
            nonlocal calls
            if path.name == "receipt.json":
                calls += 1
                if calls == 2:
                    raise OSError("disk failure")
            return write(path, data)
        with patch.object(local, "_write", side_effect=injected), self.assertRaises(OSError):
            local.install(self.candidate, self.game, self.digest)
        self.assertEqual((self.game / "AF3DN.P").read_bytes(), b"original")
        self.assertEqual(local.install(self.candidate, self.game, self.digest)["state"], "installed")


if __name__ == "__main__":
    unittest.main()
