"""Invalid numeric edits must not partially rewrite source or deployed data."""
import pytest
from plugins.bannerlord.perk_data import save_perk_definitions, save_xp_source_definitions
from plugins.bannerlord.skill_data import save_effect_definitions
from plugins.bannerlord.settings_data import save_mcm_defaults
from plugins.bannerlord.runtime_overrides import read_runtime_overrides, save_runtime_overrides
from test_bannerlord_perks_runtime import PERKS, XP
from test_bannerlord_plugin import EFFECT_DEFINITIONS
from test_bannerlord_settings import TEXT
import test_bannerlord_runtime_overrides as runtime_fixture


def test_numeric_source_rejections_preserve_entire_batch(tmp_path):
    source = tmp_path / 'src'
    source.mkdir()
    fixtures = [('CustomSkillPerks.cs', PERKS), ('CustomSkillXpSourcesConfig.cs', XP),
        ('CustomSkillEffectRanges.cs', EFFECT_DEFINITIONS), ('LexerSkillTweaksSettings.cs', TEXT)]
    for filename, text in fixtures:
        (source / filename).write_text(text, encoding='utf-8')
    before = {p.name: p.read_bytes() for p in source.iterdir()}
    for value in [True, 25.5, '25.5', float('nan'), float('inf'), -1, 101]:
        with pytest.raises(ValueError):
            save_perk_definitions(tmp_path, [{'index':1,'fields':{'description':'Valid first change'}},
                {'index':0,'fields':{'level':value}}])
        assert {p.name:p.read_bytes() for p in source.iterdir()} == before
    for writer, fields in [(save_perk_definitions, {'level':26}),
            (save_xp_source_definitions, {'defaultAmount':2}),
            (save_effect_definitions, {'defaultLow':140})]:
        for index in [True, 0.5, '0.5']:
            with pytest.raises(ValueError):
                writer(tmp_path, [{'index':index,'fields':fields}])
    for value in [True, False, float('nan'), float('inf')]:
        with pytest.raises(ValueError):
            save_xp_source_definitions(tmp_path, [{'index':0,'fields':{'defaultAmount':value}}])
        with pytest.raises(ValueError):
            save_effect_definitions(tmp_path, [{'index':0,'fields':{'defaultLow':value}}])
        with pytest.raises(ValueError):
            save_mcm_defaults(tmp_path, [{'property':'Interval','value':value}])
        assert {p.name:p.read_bytes() for p in source.iterdir()} == before
    saved = save_perk_definitions(tmp_path, [{'index':0,'fields':{'level':26}}])
    assert saved['perks'][0]['level'] == 26
    saved = save_xp_source_definitions(tmp_path, [{'index':0,'fields':{'defaultAmount':2.5}}])
    assert saved['sources'][0]['defaultAmount'] == 2.5


def test_runtime_numeric_rejections_preserve_both_files():
    temporary, project, game, deployed = runtime_fixture.BannerlordRuntimeOverrideTests().fixture()
    try:
        current = read_runtime_overrides(project, game)
        effect_id, xp_id = current['effects'][0]['id'], current['xpSources'][0]['id']
        valid = {'effects':[{'id':effect_id,'overridden':True,'low':125,'high':40}],
                 'xpSources':[{'id':xp_id,'overridden':True,'amount':8}]}
        save_runtime_overrides(project, runtime_fixture.with_runtime_revisions(project, game, valid), game)
        data = deployed / 'ModuleData'
        before = {p.name:p.read_bytes() for p in data.iterdir()}
        for field, invalid in [('amount',True), ('amount',float('nan')),
                ('amount',float('inf')), ('overridden','false'), ('overridden',1)]:
            payload = {'effects':[{'id':effect_id,'overridden':True,'low':120,'high':35}],
                'xpSources':[{'id':xp_id,'overridden':True,'amount':9,field:invalid}]}
            with pytest.raises(ValueError):
                save_runtime_overrides(project, runtime_fixture.with_runtime_revisions(project, game, payload), game)
            assert {p.name:p.read_bytes() for p in data.iterdir()} == before
        for invalid in [True, False, float('nan'), float('inf')]:
            payload = {'effects':[{'id':effect_id,'overridden':True,'low':invalid,'high':35}]}
            with pytest.raises(ValueError):
                save_runtime_overrides(project, runtime_fixture.with_runtime_revisions(project, game, payload), game)
            assert {p.name:p.read_bytes() for p in data.iterdir()} == before
    finally:
        temporary.cleanup()
