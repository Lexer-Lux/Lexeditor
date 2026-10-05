"""GF "MP" Bars tweak-mod switch, strict values, Monogamy requirement and TOML reset checks.

GF "MP" Bars is a driver-only tweak mod that requires Monogamy. A fixture
library in a temporary project stands in for the reader's; no game needed.
"""
from pathlib import Path
import json
import os
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from core import script_mods
from plugins.ff8 import gameplay_settings as settings, paths, tweak_mods

DRIVER_TWEAK='''
def build(settings, context):
    context.need_driver()
    context.ffnx(%r, True)
    return {}
'''
NAME='GF "MP" Bars'


def make(library,folder,mod_id,name,schema,key=None):
    root=library/folder;(root/'script').mkdir(parents=True)
    (root/'script'/'__init__.py').write_text('',encoding='utf-8')
    (root/'script'/'tweak.py').write_text(DRIVER_TWEAK%key if key else 'def build(settings, context):\n    return {}\n',encoding='utf-8')
    (root/'settings.schema.json').write_text(json.dumps(schema),encoding='utf-8')
    (root/'mod.json').write_text(json.dumps({'id':mod_id,'name':name,'enabled':False,'script':{'version':1}}),encoding='utf-8')
    script_mods.set_trusted(root,True)
    return root


def set_enabled(root,value):
    path=root/'mod.json';data=json.loads(path.read_text(encoding='utf-8'))
    if value is None:data.pop('enabled',None)
    else:data['enabled']=value
    path.write_text(json.dumps(data),encoding='utf-8')


def row(project,game,mod_id):
    return next(item for item in settings.load(project,game)['tweaks'] if item['id']==mod_id)


def write_config(project,library,game,config):
    """What gameplay_settings.save writes into FFNx.toml for the enabled mods."""
    built=tweak_mods.build_enabled(project,library,game,paths.BASELINE_ROOT)
    settings._set_ffnx_keys(config,{**settings.FFNX_DEFAULTS,**built['ffnx']})


def run():
    with tempfile.TemporaryDirectory(prefix='ff8-gf-settings-') as name:
        root=Path(name);project=root/'mod';game=root/'game'
        library=project/'.lexeditor-mods';game.mkdir();library.mkdir(parents=True)
        previous=os.environ.get(script_mods.TRUST_ENV);os.environ[script_mods.TRUST_ENV]=str(root/'trust.json')
        try:
            monogamy=make(library,'Monogamy','monogamy','Monogamy',{'title':'MONOGAMY','fields':[]})
            bars=make(library,'GF MP Bars','gf-mp-bars',NAME,{'title':'GF "MP" BARS','requires':['monogamy'],'needsDriver':True,'fields':[]},'enable_ff8_gf_hp_bars')
            hp=make(library,'HP Bars','hp-bars','HP Bars',{'title':'HP BARS','needsDriver':True,'fields':[]},'enable_ff8_hp_bars')
            xp=make(library,'XP Bars','xp-bars','XP Bars',{'title':'XP BARS','needsDriver':True,'fields':[]},'enable_ff8_xp_bars')
            assert settings.FFNX_DEFAULTS['enable_ff8_gf_hp_bars'] is False
            # Only a real true in mod.json switches the mod on.
            for value,expected in ((None,False),(False,False),(True,True),('true',False),(1,False)):
                set_enabled(bars,value)
                assert row(project,game,'gf-mp-bars')['enabled'] is expected,value
            assert row(project,game,'gf-mp-bars')['schema']['requires']==['monogamy']
            config=game/'FFNx.toml';config.write_text('fullscreen = true\nenable_ff8_hp_bars = true\n',encoding='utf-8')
            set_enabled(bars,True);set_enabled(monogamy,True)
            write_config(project,library,game,config)
            text=config.read_text(encoding='utf-8');assert 'enable_ff8_gf_hp_bars = true' in text
            assert 'enable_ff8_hp_bars = false' in text and 'fullscreen = true' in text
            set_enabled(bars,False);set_enabled(hp,True);set_enabled(xp,True)
            write_config(project,library,game,config)
            text=config.read_text(encoding='utf-8')
            assert text.count('enable_ff8_gf_hp_bars = false')==1 and 'enable_ff8_gf_hp_bars = true' not in text
            assert 'enable_ff8_hp_bars = true' in text and 'enable_ff8_xp_bars = true' in text
            # Save refuses a switch that is not a real true or false, naming the tweak.
            for bad in ('true',1,[],{}):
                try: settings.save({'tweaks':{'gf-mp-bars':{'enabled':bad}}},game_root=game,project_root=project)
                except ValueError as error: assert NAME in str(error),error
                else: raise AssertionError('Invalid GF bar value was accepted')
            # It also refuses GF "MP" Bars without Monogamy, and keeps the old switches.
            set_enabled(monogamy,False);set_enabled(hp,False);set_enabled(xp,False)
            try: settings.save({'tweaks':{'gf-mp-bars':{'enabled':True}}},game_root=game,project_root=project)
            except ValueError as error: assert NAME in str(error) and 'monogamy' in str(error),error
            else: raise AssertionError('GF "MP" Bars was enabled without Monogamy')
            assert row(project,game,'gf-mp-bars')['enabled'] is False
            saved=settings.save({'tweaks':{'gf-mp-bars':{'enabled':True},'monogamy':{'enabled':True}}},game_root=game,project_root=project)
            assert {item['id'] for item in saved['tweaks'] if item['enabled']}=={'gf-mp-bars','monogamy'}
        finally:
            if previous is None:os.environ.pop(script_mods.TRUST_ENV,None)
            else:os.environ[script_mods.TRUST_ENV]=previous
    # The page and the modules it loads: every tweak mod's switch is named after it.
    ui=chr(10).join(path.read_text(encoding='utf-8') for path in [ROOT/'plugins/ff8/editor.html',*sorted((ROOT/'plugins/ff8').glob('*.js'))])
    assert '"aria-label":row.name' in ui
    assert 'platformConfigView({config:state.platformConfig,showHeader:false,' in ui
    print('PASS: GF-bar switch, strict values, Monogamy requirement, per-mod reset, independent TOML toggles, and UI wiring.')

if __name__=='__main__':run()
