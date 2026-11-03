"""Profile candidates require exact finite HP equality, never rounding."""
import pytest
from plugins.rdr2 import server as s


@pytest.mark.parametrize('bad',['NaN','Infinity','-Infinity','',None,'10_0','invalid','0','-1'])
def test_unproven_health_values_do_not_become_candidates(bad):
    assert s._mob_health_value(bad) is None


def test_fractional_and_large_observations_match_exactly(tmp_path,monkeypatch):
    rows=[{'section':'HealthConfig','name':name,'fields':[{'field':'DefaultEnergy','value':value}]} for name,value in [('TEN','10'),('FRACTION','10.4'),('LARGE','9007199254740993'),('NAN','NaN'),('INF','Infinity')]]
    monkeypatch.setattr(s,'get_mobs',lambda ds:{'health':{'records':rows}})
    roster=tmp_path/'roster.csv';roster.write_text('model,group\nINTEGER,gang\nFRACTION,gang\nUNMATCHED,gang\nLARGE,gang\nINVALID,gang\n')
    probe=tmp_path/'probe.csv';probe.write_text('model,max_health,status\nINTEGER,10.0,ok\nFRACTION,10.4,ok\nUNMATCHED,10.9,ok\nLARGE,9007199254740993,ok\nINVALID,Infinity,ok\n')
    monkeypatch.setattr(s,'MOB_ROSTER_FILE',roster);monkeypatch.setattr(s,'MOB_PROBE_FILE',probe);monkeypatch.setattr(s,'MOB_DISCOVERED_FILE',tmp_path/'absent.csv')
    before={path:path.read_bytes() for path in [roster,probe]}
    result={row['model']:row for row in s.get_mob_models()['models']}
    assert result['INTEGER']['observedHealth']==10 and result['INTEGER']['candidates']==['TEN']
    assert result['FRACTION']['observedHealth']=='10.4' and result['FRACTION']['candidates']==['FRACTION']
    assert result['UNMATCHED']['observedHealth']=='10.9' and result['UNMATCHED']['candidates']==[]
    assert result['LARGE']['observedHealth']=='9007199254740993' and result['LARGE']['candidates']==['LARGE']
    assert result['INVALID']['observedHealth'] is None and result['INVALID']['candidates']==[]
    assert {path:path.read_bytes() for path in before}==before
