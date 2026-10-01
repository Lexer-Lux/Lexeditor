"""Terrain labels stay project-local and never alter game world binaries."""
import pytest
from plugins.ff8 import world_names, world_map


def test_ground_labels_save_reset_and_isolate_sources(tmp_path,monkeypatch):
    monkeypatch.setattr(world_names.paths,'PROJECT_ROOT',tmp_path)
    monkeypatch.setattr(world_map,'source_path',lambda *_: pytest.fail('A label save must not read or write world binaries'))
    result=world_map.save([{'kind':'groundName','id':6,'name':'Meadow'}])
    assert result['saved']==1
    assert world_names.load()=={'6':'Meadow'}
    assert world_names.load('vanilla')=={}
    assert world_names.load('reference:example')=={}
    world_map.save([{'kind':'groundName','id':7,'name':'Rock'}])
    world_map.save([{'kind':'groundName','id':6,'name':''}])
    assert world_names.load()=={'7':'Rock'}
    assert [p.name for p in tmp_path.iterdir()]==[world_names.FILENAME]


@pytest.mark.parametrize('edit',[
    {'id':-1,'name':'Bad'},{'id':256,'name':'Bad'},{'id':True,'name':'Bad'},
    {'id':1.2,'name':'Bad'},{'id':6,'name':'x'*121},{'id':6,'name':'Two\nlines'},
    {'id':6,'name':None},
])
def test_invalid_batch_keeps_previous_names(tmp_path,monkeypatch,edit):
    monkeypatch.setattr(world_names.paths,'PROJECT_ROOT',tmp_path)
    destination=world_names.write({'6':'Meadow'})
    before=destination.read_bytes()
    with pytest.raises(ValueError):
        world_map.save([{'kind':'groundName','id':6,'name':'Changed'},dict(edit,kind='groundName')])
    assert destination.read_bytes()==before
