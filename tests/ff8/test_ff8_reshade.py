"""FF8's ReShade hook: a dxgi loader beside FF8_EN.exe, with sane defaults.

FFNx renders through bgfx (Direct3D 11/12 on Windows under Auto), which
ReShade hooks through dxgi.dll. The slot is free (FFNx's own loader is
AF3DN.P) and the game is 32-bit, so the ReShade32 build goes in.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import reshade_effects
from core import reshade_projects
from plugins.ff8.plugin import PLUGIN


def _fake_exe(path: Path, bits: int = 32) -> None:
    head = bytearray(b"MZ" + b"\0" * 62)
    head[0x3C:0x40] = (0x40).to_bytes(4, "little")
    machine = 0x014C if bits == 32 else 0x8664
    path.write_bytes(bytes(head) + b"PE\0\0" + machine.to_bytes(2, "little"))


def _fake_reshade_dll(path: Path) -> None:
    path.write_bytes(b"MZ" + b"\0" * 64 + reshade_projects.RESHADE_MARKER + b"\0" * 64)


class FF8ReshadeTests(unittest.TestCase):
    def test_declaration_names_dxgi_at_the_root(self):
        installation = PLUGIN.installation
        self.assertEqual(installation.reshade_renderer, "dxgi")
        self.assertEqual(installation.reshade_root, "")

    def test_defaults_enable_gentle_sharpening_only(self):
        path = Path(__file__).resolve().parents[2] / "plugins" / "ff8" / "reshade-defaults.ini"
        self.assertTrue(path.is_file(), "FF8 ships no ReShade defaults")
        top, sections = reshade_effects.read_preset(path)
        effects = reshade_effects.catalogue()
        known = {row["file"] for row in effects}
        enabled = [item.split("@", 1)[-1] for item in top.get("Techniques", "").split(",") if item]
        self.assertEqual(enabled, ["Sharpen.fx"])
        self.assertTrue(all(item.split("@", 1)[-1] in known
                            for item in top.get("TechniqueSorting", "").split(",")),
                        "TechniqueSorting names an effect Lexeditor does not ship")
        self.assertEqual(sections.get("Sharpen.fx", {}).get("Strength"), "0.500000")

    def test_state_from_defaults_matches_the_shipped_look(self):
        source = Path(__file__).resolve().parents[2] / "plugins" / "ff8" / "reshade-defaults.ini"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / reshade_effects.DEFAULT_PRESET).write_bytes(source.read_bytes())
            state = reshade_effects.state(root, source)
        self.assertTrue(state["hasDefaults"])
        on = sorted(row["file"] for row in state["effects"] if row["enabled"])
        self.assertEqual(on, ["Sharpen.fx"])

    def test_dxgi_hook_installs_detects_and_removes_cleanly(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "game"
            root.mkdir()
            store = Path(temporary) / "store"
            store.mkdir()
            exe = root / "FF8_EN.exe"
            _fake_exe(exe)
            (root / "AF3DN.P").write_bytes(b"fake-ffnx-loader")
            _fake_reshade_dll(store / reshade_projects.STORE_DLL32)
            with patch.object(reshade_projects, "STORE", store):
                self.assertEqual(reshade_projects.loader_bits(root, exe), 32)
                self.assertEqual(reshade_projects.occupied_loaders(root), [])
                result = reshade_projects.install(root, "dxgi", exe)
                self.assertEqual(result["renderer"], "dxgi")
                self.assertEqual(result["bits"], 32)
                target = root / "dxgi.dll"
                self.assertTrue(target.is_file())
                self.assertTrue(reshade_projects.is_reshade(target))
                self.assertEqual(reshade_projects.installed_renderer(root), "dxgi")
                self.assertEqual((root / "AF3DN.P").read_bytes(), b"fake-ffnx-loader")
                removed = reshade_projects.uninstall(root)
                self.assertEqual([entry["renderer"] for entry in removed["removed"]], ["dxgi"])
                self.assertFalse(target.exists())
                self.assertTrue((root / "AF3DN.P").is_file())

    def test_a_foreign_dxgi_dll_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "game"
            root.mkdir()
            store = Path(temporary) / "store"
            store.mkdir()
            exe = root / "FF8_EN.exe"
            _fake_exe(exe)
            (root / "dxgi.dll").write_bytes(b"MZ" + b"someone-elses-wrapper")
            _fake_reshade_dll(store / reshade_projects.STORE_DLL32)
            with patch.object(reshade_projects, "STORE", store):
                self.assertEqual(
                    [entry["dll"] for entry in reshade_projects.occupied_loaders(root)],
                    ["dxgi.dll"])
                with self.assertRaisesRegex(ValueError, "will not overwrite"):
                    reshade_projects.install(root, "dxgi", exe)


if __name__ == "__main__":
    unittest.main()
