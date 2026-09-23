"""Synthetic acceptance for pinned FFNx acquisition and guarded 2026 setup."""
from __future__ import annotations

import hashlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from plugins.ff7 import tooling


class FFNxToolingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.game = self.root / "game"
        self.work = self.game / "ff7" / "workingdir"
        self.work.mkdir(parents=True)
        self.exe = self.game / "ff7" / "resources" / "ff7_1.02" / "ff7_en"
        self.exe.parent.mkdir(parents=True)
        self.exe.write_bytes(b"installed executable fixture")
        self.window = self.work / "data" / "lang-ja" / "kernel" / "window.bin"
        self.window.parent.mkdir(parents=True)
        self.window.write_bytes(b"installed window fixture")
        self.user_data = self.root / "user-data"
        self.patcher = mock.patch.object(tooling, "user_data_dir", lambda: self.user_data)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def archive(self, entries=None) -> Path:
        path = self.root / "FFNx-Steam.zip"
        values = {"FFNx.toml": 'direct_mode_path = "direct"\n', "FFNx.dll": b"runtime"}
        values.update(entries or {})
        with zipfile.ZipFile(path, "w") as package:
            for name, raw in values.items():
                package.writestr(name, raw)
        return path

    def pin(self, archive: Path):
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        return mock.patch.object(tooling, "FFNX_SHA256", digest)

    def test_first_time_setup_is_pinned_owned_and_preserves_installed_sources(self):
        archive = self.archive()
        original_exe, original_window = self.exe.read_bytes(), self.window.read_bytes()
        with self.pin(archive):
            result = tooling.install_pinned(self.game, archive)
            self.assertTrue(result["setup"])
            self.assertTrue(result["installed"])
            self.assertTrue(result["owned"])
            self.assertEqual((self.work / "FFNx.dll").read_bytes(), b"runtime")
            self.assertEqual((self.work / "ff7_en.exe").read_bytes(), original_exe)
            self.assertEqual((self.work / "data/kernel/windows.bin").read_bytes(), original_window)
            self.assertEqual((self.work / "steam_appid.txt").read_text(encoding="ascii"), "3837340\n")
            self.assertTrue((self.work / tooling.SETUP_MANIFEST).is_file())
            tooling.install_pinned(self.game, archive)
        self.assertEqual(self.exe.read_bytes(), original_exe)
        self.assertEqual(self.window.read_bytes(), original_window)

    def test_owned_setup_updates_pinned_payload_and_removes_stale_owned_files(self):
        old = self.archive({"FFNx.dll": b"old runtime", "old-only.dll": b"stale"})
        with self.pin(old):
            tooling.install_pinned(self.game, old)
        self.assertEqual((self.work / "FFNx.dll").read_bytes(), b"old runtime")
        self.assertTrue((self.work / "old-only.dll").is_file())

        new = self.root / "FFNx-Steam-new.zip"
        with zipfile.ZipFile(new, "w") as package:
            package.writestr("FFNx.toml", 'direct_mode_path = "direct"\n')
            package.writestr("FFNx.dll", b"new runtime")
        with self.pin(new):
            result = tooling.install_pinned(self.game, new)
        self.assertTrue(result["owned"])
        self.assertEqual((self.work / "FFNx.dll").read_bytes(), b"new runtime")
        self.assertFalse((self.work / "old-only.dll").exists())

    def test_external_install_and_external_changes_are_never_overwritten(self):
        archive = self.archive()
        (self.work / "FFNx.toml").write_text("external\n", encoding="utf-8")
        with self.pin(archive), self.assertRaisesRegex(ValueError, "not Lexeditor-owned"):
            tooling.install_pinned(self.game, archive)
        self.assertEqual((self.work / "FFNx.toml").read_text(encoding="utf-8"), "external\n")

        (self.work / "FFNx.toml").unlink()
        with self.pin(archive):
            tooling.install_pinned(self.game, archive)
            (self.work / "FFNx.dll").write_bytes(b"changed by another tool")
            with self.assertRaisesRegex(ValueError, "changed outside Lexeditor"):
                tooling.install_pinned(self.game, archive)
        self.assertEqual((self.work / "FFNx.dll").read_bytes(), b"changed by another tool")

    def test_archive_paths_are_contained(self):
        archive = self.root / "unsafe.zip"
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr("FFNx.toml", "x")
            package.writestr("../escape.dll", "bad")
        with self.pin(archive), self.assertRaisesRegex(ValueError, "Unsafe FFNx archive path"):
            tooling.install_pinned(self.game, archive)
        self.assertFalse((self.root / "escape.dll").exists())

    def test_download_is_hash_checked_before_cache_use(self):
        archive = self.archive()
        raw = archive.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        with mock.patch.object(tooling, "FFNX_SHA256", digest):
            path = tooling.acquire_archive(opener=lambda url, timeout=60: io.BytesIO(raw))
            self.assertEqual(path.read_bytes(), raw)
            self.assertEqual(tooling.acquire_archive().read_bytes(), raw)
        path.unlink()
        with mock.patch.object(tooling, "FFNX_SHA256", "0" * 64), self.assertRaisesRegex(RuntimeError, "SHA-256 mismatch"):
            tooling.acquire_archive(opener=lambda url, timeout=60: io.BytesIO(raw))

    def test_missing_installed_prerequisite_fails_before_runtime_mutation(self):
        archive = self.archive()
        self.window.unlink()
        with self.pin(archive), self.assertRaisesRegex(FileNotFoundError, "requires installed source"):
            tooling.install_pinned(self.game, archive)
        self.assertFalse((self.work / "FFNx.toml").exists())
        self.assertFalse((self.work / tooling.SETUP_MANIFEST).exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
