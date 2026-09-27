"""Troop copies append active IDs without changing equipment, cut rows or upgrades."""
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from plugins.warband.troop_editor import create_troop,troop_data
from test_warband_troop_editor import SOURCE


def test_copy_troop_preserves_unknown_fields_and_upgrade_code(tmp_path):
    source=tmp_path/'module_troops.py';source.write_text(SOURCE,encoding='utf-8')
    original=source.read_bytes();data=troop_data(tmp_path)
    result=create_troop(tmp_path,data['sha256'],0,'soldier','new_soldier','New soldier','New soldiers')
    after=troop_data(tmp_path)
    assert [r['id'] for r in after['rows'] if r['status']!='CUT']==['soldier','new_soldier']
    new=next(r for r in after['rows'] if r['id']=='new_soldier')
    assert new['recordIndex']==result['recordIndex']
    assert new['name']=='New soldier' and new['plural']=='New soldiers'
    assert {k:v for k,v in new['fields'].items() if k not in ('id','name','plural')}=={
        k:v for k,v in data['rows'][0]['fields'].items() if k not in ('id','name','plural')}
    assert '## ["cut", "Cut", "Cut troops"' in source.read_text()
    assert source.read_text().endswith('upgrade(troops, "soldier", "cut")\n')
    assert Path(result['backup']).read_bytes()==original


@pytest.mark.parametrize('index,old,new,name,plural',[
    (0,'soldier','cut','New','News'),(0,'wrong','new','New','News'),
    (1,'cut','new','New','News'),(True,'soldier','new','New','News'),
    (0,'soldier','bad id','New','News'),(0,'soldier','new','','News')])
def test_copy_troop_refuses_invalid_request_without_writing(tmp_path,index,old,new,name,plural):
    source=tmp_path/'module_troops.py';source.write_text(SOURCE,encoding='utf-8')
    original=source.read_bytes();data=troop_data(tmp_path)
    with pytest.raises(ValueError):create_troop(tmp_path,data['sha256'],index,old,new,name,plural)
    assert source.read_bytes()==original
