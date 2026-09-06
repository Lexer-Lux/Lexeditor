"""Offline GF HP option persistence and independent FFNx activation tests."""
from pathlib import Path
import json
import sys
import tempfile
import tomllib
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from games.ff8 import gameplay_settings as settings


def main():
    with tempfile.TemporaryDirectory() as name:
        root = Path(name)
        game, project = root / 'game', root / 'project'
        game.mkdir(); project.mkdir()
        settings.initialize_project(project)
        assert settings.load(project, game)['gfHpBars'] is False
        config = game / 'FFNx.toml'
        config.write_text('other_setting = true\nenable_ff8_hp_bars = false\n', encoding='utf-8')
        with patch.object(settings, '_verify_executable', return_value=game / 'FF8_EN.exe'):
            for enabled in (True, False, True):
                result = settings.save({'flyingEvaBonus': 25, 'gfHpBars': enabled},
                                       game_root=game, project_root=project, install_runtime=False)
                assert result['gfHpBars'] is enabled
                assert settings.load(project, game)['gfHpBars'] is enabled
                settings._set_ffnx_runtime_tweaks(config, xp_bars=False, hp_bars=False,
                                                  better_targeting=False, gf_hp_bars=enabled)
                parsed = tomllib.loads(config.read_text(encoding='utf-8'))
                assert parsed['enable_ff8_gf_hp_bars'] is enabled
                assert parsed['enable_ff8_hp_bars'] is False and parsed['other_setting'] is True
                assert config.read_text().count('enable_ff8_gf_hp_bars =') == 1
            for invalid in ('true', 1, [], {}):
                before = settings.settings_path(project).read_bytes()
                try:
                    settings.save({'flyingEvaBonus': 25, 'gfHpBars': invalid}, game_root=game, project_root=project)
                except ValueError as error:
                    assert 'GF HP Bars' in str(error)
                else:
                    raise AssertionError(f'Invalid GF toggle accepted: {invalid!r}')
                assert settings.settings_path(project).read_bytes() == before
        data = json.loads(settings.settings_path(project).read_text())
        for invalid in ('true', 1, [], {}):
            data['gfHpBars'] = invalid
            settings.settings_path(project).write_text(json.dumps(data))
            assert settings.load(project, game)['gfHpBars'] is False
        data.pop('gfHpBars')
        settings.settings_path(project).write_text(json.dumps(data))
        assert settings.load(project, game)['gfHpBars'] is False
    print('PASS: GF HP default off; persistence; invalid-value rejection; independent, idempotent FFNx toggle')


if __name__ == '__main__':
    main()
