"""GF HP-bar per-mod settings and TOML reset checks; no game installation."""
from pathlib import Path
import json
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from games.ff8 import gameplay_settings as settings


def run():
    with tempfile.TemporaryDirectory(prefix='ff8-gf-settings-') as name:
        root=Path(name);project=root/'mod';game=root/'game'
        project.mkdir();game.mkdir()
        path=settings.settings_path(project);path.parent.mkdir(parents=True,exist_ok=True)
        for value,expected in ((None,False),(False,False),(True,True),('true',False),(1,False)):
            path.write_text(json.dumps({} if value is None else {'gfHpBars':value}))
            assert settings.load(project,game)['gfHpBars'] is expected
        config=game/'FFNx.toml';config.write_text('fullscreen = true\nenable_ff8_hp_bars = true\n')
        settings._set_ffnx_runtime_tweaks(config,xp_bars=False,hp_bars=False,better_targeting=False,gf_hp_bars=True)
        text=config.read_text();assert 'enable_ff8_gf_hp_bars = true' in text
        assert 'enable_ff8_hp_bars = false' in text and 'fullscreen = true' in text
        settings._set_ffnx_runtime_tweaks(config,xp_bars=True,hp_bars=True,better_targeting=False)
        assert config.read_text().count('enable_ff8_gf_hp_bars = false')==1
        assert 'enable_ff8_gf_hp_bars = true' not in config.read_text()
        settings.initialize_project(project)
        assert json.loads(path.read_text())['gfHpBars'] is False
        for bad in ('true',1,[],{}):
            try: settings.save({**settings.load(project,game),'gfHpBars':bad},game_root=game,project_root=project)
            except ValueError as error: assert 'GF HP Bars' in str(error)
            else: raise AssertionError('Invalid GF bar value was accepted')
        assert 'gfHpBars' in settings.ACCEPTED_TWEAKS
    ui=(ROOT/'games/ff8/editor.html').read_text()
    assert 'gfHpBars:state.data.settings.gfHpBars' in ui
    assert '"aria-label":"GF HP Bars"' in ui
    assert 'platformConfigView({config:state.platformConfig,showHeader:false,' in ui
    print('PASS: GF-bar defaults, strict values, per-mod reset, independent TOML toggles, and UI wiring.')

if __name__=='__main__':run()
