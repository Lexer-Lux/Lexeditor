"""Persist and compose the supported spell-stock combinations using real saves.

Only executable identity verification is stubbed when --exe is absent. All
settings validation, JSON/TOML serialization and runtime-tree composition are
production code; no installed game is touched. Driver installation has its own
byte-pinned Windows smoke test.
"""
from __future__ import annotations
import argparse
from contextlib import nullcontext
import json
from pathlib import Path
import shutil
import sys
import tempfile
import tomllib
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from games.ff8 import gameplay_settings as settings


def run(exe:Path|None=None) -> None:
    with tempfile.TemporaryDirectory(prefix='ff8-stock-settings-') as directory:
        root=Path(directory);project=root/'mod';game=root/'game';runtime=root/'runtime'
        project.mkdir();game.mkdir()
        if exe:shutil.copyfile(exe,game/'FF8_EN.exe')
        settings.initialize_project(project)
        for key in ('noMagicConsumption','dropsAfterMug'):
            assert key in settings.ACCEPTED_TWEAKS
            assert settings.load(project,game)[key] is False
            for bad in ('true',1,[],{}):
                try:settings.save({**settings.load(project,game),key:bad},game,project,runtime_root=runtime)
                except ValueError:pass
                else:raise AssertionError('Accepted invalid '+key)
        with nullcontext() if exe else patch.object(settings,'_verify_executable',return_value=game/'FF8_EN.exe'):
            for cap in (1,2,10,99,100,127,128,150,254,255):
                for shared in (False,True):
                    for switch in (False,True):
                        for no_consume in (False,True):
                            data=settings.load(project,game)
                            data.update(sharedMagicInventory=shared,partySwitch=switch,
                                noMagicConsumption=no_consume,dropsAfterMug=True,
                                maxSpellEnabled=True,maxSpell=cap)
                            settings.save(data,game,project,runtime_root=runtime)
                            saved=settings.load(project,game)
                            for key in ('sharedMagicInventory','partySwitch','noMagicConsumption','dropsAfterMug','maxSpellEnabled','maxSpell'):
                                assert saved[key]==data[key],(cap,shared,switch,key)
                            config=tomllib.loads(settings.shared_magic_runtime_config.path(project).read_text(encoding='utf-8'))
                            assert config['sharedMagicInventory'] is shared and config['magicStockLimit']==cap
                            assert '486668 = 00' in settings.patch_path(project).read_text(encoding='utf-8')
                            assert settings.patch_path(project).read_bytes()==settings.materialized_runtime_patch_path(runtime).read_bytes()
            data=settings.load(project,game)
            data.update(noMagicConsumption=False,dropsAfterMug=False,maxSpellEnabled=False)
            settings.save(data,game,project,runtime_root=runtime)
            assert '486668 = 00' not in settings.patch_path(project).read_text(encoding='utf-8')
            config=tomllib.loads(settings.shared_magic_runtime_config.path(project).read_text(encoding='utf-8'))
            assert config['magicStockLimit']==100
        config=game/'FFNx.toml';config.write_text('fullscreen = true\ncustom_setting = "retained"\n',encoding='utf-8')
        for enabled in (True,False):
            settings._set_ffnx_runtime_tweaks(config,xp_bars=False,hp_bars=False,
                better_targeting=False,party_switch=True,no_magic_consumption=enabled)
            parsed=tomllib.loads(config.read_text(encoding='utf-8'))
            assert parsed['enable_ff8_no_magic_consumption'] is enabled
            assert parsed['enable_ff8_party_switch'] is True
            assert parsed['custom_setting']=='retained' and parsed['fullscreen'] is True
        settings.initialize_project(project)
        assert not settings.load(project,game)['noMagicConsumption']
        assert not settings.load(project,game)['dropsAfterMug']
    ui=(ROOT/'games/ff8/editor.html').read_text(encoding='utf-8')
    for key,label in [('noMagicConsumption','No Magic Consumption'),('dropsAfterMug','Drops After Mug')]:
        assert f'{key}:state.data.settings.{key}' in ui
        assert f'"aria-label":"{label}"' in ui
    print('PASS: 80 real settings saves/compositions with shared/private stocks, Party Switch, no consumption and ten cap boundaries; strict booleans, off defaults, reset and unrelated FFNx options preserved.')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--exe',type=Path)
    run(parser.parse_args().exe)
