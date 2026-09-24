from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from plugins.terraria.runtime import SUPPORTED_TML_DISPLAY, inspect_runtime, parse_build_identifier


class TerrariaRuntimeTests(unittest.TestCase):
    def test_parses_official_build_identifier_shape(self):
        state = parse_build_identifier(
            "1.4.4.9+2026.7.3.0|2026.7|stable|Stable|deadbeef|0"
        )
        self.assertEqual(state["version"], (2026, 7, 3, 0))
        self.assertEqual(state["displayVersion"], "2026.07.3.0")
        self.assertEqual(state["purpose"], "Stable")

    def test_exact_supported_stable_version_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tModLoader.dll").write_bytes(b"fixture")
            state = inspect_runtime(
                root,
                platform_name="nt",
                version_reader=lambda _path: "1.4.4.9+2026.7.3.0|2026.7|stable|Stable|deadbeef|0",
            )
            self.assertTrue(state["runtimeSupported"])
            self.assertEqual(state["runtimeVersion"], SUPPORTED_TML_DISPLAY)

    def test_preview_and_other_versions_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tModLoader.dll").write_bytes(b"fixture")
            preview = inspect_runtime(
                root,
                platform_name="nt",
                version_reader=lambda _path: "1.4.4.9+2026.7.3.0|2026.7|preview|Preview|deadbeef|0",
            )
            self.assertFalse(preview["runtimeSupported"])
            self.assertIn("stable", preview["runtimeReason"].lower())
            newer = inspect_runtime(
                root,
                platform_name="nt",
                version_reader=lambda _path: "1.4.4.9+2026.8.2.1|2026.7|stable|Stable|deadbeef|0",
            )
            self.assertFalse(newer["runtimeSupported"])
            self.assertIn(SUPPORTED_TML_DISPLAY, newer["runtimeReason"])

    def test_unreadable_version_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tModLoader.dll").write_bytes(b"fixture")
            state = inspect_runtime(
                root,
                platform_name="nt",
                version_reader=lambda _path: "",
            )
            self.assertFalse(state["runtimeSupported"])
            self.assertIn("version", state["runtimeReason"].lower())


if __name__ == "__main__":
    unittest.main()
