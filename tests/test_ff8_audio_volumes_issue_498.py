"""Separate SFX/Music volume gains for the editor half of issue #498.

The in-game Config-menu replacement still needs a game session, but the
editor side is fully testable: two bounded gains travel from the Tweaks
page through per-mod settings into FFNx.toml on launch, one category
each, without touching the other.
"""
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from plugins.ff8 import gameplay_settings

ROOT = Path(__file__).resolve().parents[1]


class AudioVolumeSettingsTests(unittest.TestCase):
    def test_defaults_leave_both_layers_unmanaged(self):
        self.assertIsNone(gameplay_settings.DEFAULT_SFX_VOLUME)
        self.assertIsNone(gameplay_settings.DEFAULT_MUSIC_VOLUME)
        self.assertEqual(gameplay_settings.MIN_AUDIO_VOLUME, 0)
        self.assertEqual(gameplay_settings.MAX_AUDIO_VOLUME, 100)

    def test_load_defaults_and_round_trip(self):
        with tempfile.TemporaryDirectory(prefix="ff8-audio-volumes-") as directory:
            project = Path(directory)
            defaults = gameplay_settings.load(project)
            self.assertIsNone(defaults["sfxVolume"])
            self.assertIsNone(defaults["musicVolume"])
            self.assertEqual(defaults["audioVolumeMinimum"], 0)
            self.assertEqual(defaults["audioVolumeMaximum"], 100)
            gameplay_settings.settings_path(project).write_text(
                '{"sfxVolume": 80, "musicVolume": 60}', encoding="utf-8",
            )
            stored = gameplay_settings.load(project)
            self.assertEqual(stored["sfxVolume"], 80)
            self.assertEqual(stored["musicVolume"], 60)

    def test_load_falls_back_to_unmanaged_on_garbage(self):
        with tempfile.TemporaryDirectory(prefix="ff8-audio-volumes-") as directory:
            project = Path(directory)
            gameplay_settings.settings_path(project).write_text(
                '{"sfxVolume": "loud", "musicVolume": 500}', encoding="utf-8",
            )
            stored = gameplay_settings.load(project)
            self.assertIsNone(stored["sfxVolume"])
            self.assertIsNone(stored["musicVolume"])

    def test_validator_accepts_unset_and_whole_gains_only(self):
        check = gameplay_settings._bounded_audio_volume
        self.assertIsNone(check(None, "SFX volume"))
        self.assertEqual(check(0, "SFX volume"), 0)
        self.assertEqual(check(100, "Music volume"), 100)
        self.assertEqual(check("80", "SFX volume"), 80)
        for bad in (True, False, -1, 101, "loud", 80.5, [], {}):
            with self.assertRaises(ValueError, msg=repr(bad)):
                check(bad, "SFX volume")

    def _save_data(self, project, **overrides):
        data = gameplay_settings.load(project)
        data.update(overrides)
        return data

    def test_save_persists_both_gains(self):
        with tempfile.TemporaryDirectory(prefix="ff8-audio-volumes-") as directory:
            project = Path(directory)
            fake_exe = project / "FF8_EN.exe"
            fake_exe.write_bytes(b"fake")
            with mock.patch.object(
                gameplay_settings, "_verify_executable", return_value=fake_exe,
            ), mock.patch.object(
                gameplay_settings.runtime_layout, "compose", return_value=None,
            ):
                gameplay_settings.save(
                    self._save_data(project, sfxVolume=80, musicVolume=60),
                    game_root=project, project_root=project,
                )
            import json
            stored = json.loads(
                gameplay_settings.settings_path(project).read_text(encoding="utf-8")
            )
            self.assertEqual(stored["sfxVolume"], 80)
            self.assertEqual(stored["musicVolume"], 60)

    def test_save_rejects_an_out_of_range_gain(self):
        with tempfile.TemporaryDirectory(prefix="ff8-audio-volumes-") as directory:
            project = Path(directory)
            fake_exe = project / "FF8_EN.exe"
            fake_exe.write_bytes(b"fake")
            with mock.patch.object(
                gameplay_settings, "_verify_executable", return_value=fake_exe,
            ), mock.patch.object(
                gameplay_settings.runtime_layout, "compose", return_value=None,
            ):
                with self.assertRaises(ValueError):
                    gameplay_settings.save(
                        self._save_data(project, sfxVolume=101),
                        game_root=project, project_root=project,
                    )

    def _launch_game(self, project):
        game = project / "game"
        game.mkdir()
        runtime_direct = project / ".lexeditor-runtime" / "direct"
        runtime_direct.mkdir(parents=True)
        import os
        (game / "FFNx.toml").write_text(
            f'direct_mode_path = "{os.path.relpath(runtime_direct, game)}"\n'
            "external_sfx_volume = -1\n"
            "external_music_volume = -1\n",
            encoding="utf-8",
        )
        return game

    def test_launch_writes_each_gain_to_its_own_ffnx_key(self):
        with tempfile.TemporaryDirectory(prefix="ff8-audio-volumes-") as directory:
            project = Path(directory)
            game = self._launch_game(project)
            fake_exe = project / "FF8_EN.exe"
            fake_exe.write_bytes(b"fake")
            with mock.patch.object(
                gameplay_settings, "_verify_executable", return_value=fake_exe,
            ), mock.patch.object(
                gameplay_settings.runtime_layout, "compose", return_value=None,
            ), mock.patch.object(
                gameplay_settings.ffnx_manager, "_set_project_paths",
                return_value=None,
            ):
                gameplay_settings.save(
                    self._save_data(project, sfxVolume=80, musicVolume=60),
                    game_root=game, project_root=project, install_runtime=True,
                )
            text = (game / "FFNx.toml").read_text(encoding="utf-8")
            self.assertIn("external_sfx_volume = 80", text)
            self.assertIn("external_music_volume = 60", text)

    def test_launch_leaves_unmanaged_layers_at_auto_detect(self):
        with tempfile.TemporaryDirectory(prefix="ff8-audio-volumes-") as directory:
            project = Path(directory)
            game = self._launch_game(project)
            fake_exe = project / "FF8_EN.exe"
            fake_exe.write_bytes(b"fake")
            with mock.patch.object(
                gameplay_settings, "_verify_executable", return_value=fake_exe,
            ), mock.patch.object(
                gameplay_settings.runtime_layout, "compose", return_value=None,
            ), mock.patch.object(
                gameplay_settings.ffnx_manager, "_set_project_paths",
                return_value=None,
            ):
                gameplay_settings.save(
                    self._save_data(project, musicVolume=45),
                    game_root=game, project_root=project, install_runtime=True,
                )
            text = (game / "FFNx.toml").read_text(encoding="utf-8")
            self.assertIn("external_sfx_volume = -1", text)
            self.assertIn("external_music_volume = 45", text)

    def test_editor_exposes_two_matching_sliders(self):
        editor = (ROOT / "plugins/ff8/boot.js").read_text(encoding="utf-8")
        self.assertIn('"aria-label":"SFX volume"', editor)
        self.assertIn('"aria-label":"Music volume"', editor)
        self.assertIn('row("SFX VOLUME"', editor)
        self.assertIn('row("MUSIC VOLUME"', editor)
        self.assertIn("sfxVolume:state.data.settings.sfxVolume", editor)
        self.assertIn("musicVolume:state.data.settings.musicVolume", editor)


if __name__ == "__main__":
    unittest.main()
