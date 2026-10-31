"""Repeated Save cannot create conflicting raw/portable targets in one mod."""
import pytest

from core import plugin_files
from plugins.ds1 import record_edits,texts
from plugins.ds1.formats import ItemDocument
from plugins.ds1.store import ItemStore,MARKER,RELATIVE
from ds1_fixture import make_archive,make_text_archive
from test_ds1_portable_maps import MAP,VANILLA,ENEMY,edited


def setup(tmp_path):
    game,project=tmp_path/'game',tmp_path/'project'
    (game/RELATIVE).parent.mkdir(parents=True)
    params=make_archive();(game/RELATIVE).write_bytes(params)
    project.mkdir();(project/MARKER).touch()
    maps={MAP:record_edits.create(MAP,VANILLA,edited((ENEMY,'posX',10.)))}
    (project/record_edits.FILENAME).write_bytes(record_edits.encode(maps))
    return game,project,params,maps


@pytest.mark.parametrize('existing_archive',[False,True])
def test_map_records_do_not_convert_raw_item_targets_on_repeated_save(tmp_path,existing_archive):
    game,project,params,maps=setup(tmp_path)
    if existing_archive:
        (project/RELATIVE).parent.mkdir(parents=True)
        (project/RELATIVE).write_bytes(params)
    store=ItemStore(game,project,False)
    for price in (12,17):
        store.edit('EquipParamGoods',100,'sellValue',price)
        store.save();store.save()
        saved=record_edits.project_specs(project)
        assert saved[MAP]==maps[MAP]
        assert (RELATIVE in saved) is (not existing_archive)
        assert (project/RELATIVE).exists() is existing_archive
        assert ItemStore(game,project,False).get().value('EquipParamGoods',100,'sellValue')==price
        assert (game/RELATIVE).read_bytes()==params


def test_unchanged_item_save_does_not_export_or_create_an_archive(tmp_path,monkeypatch):
    game,project,_params,maps=setup(tmp_path)
    store=ItemStore(game,project,False);store.get()
    monkeypatch.setattr(ItemDocument,'export',lambda *a,**k:pytest.fail('Unchanged items must not rebuild an archive'))
    store.save()
    assert not (project/RELATIVE).exists()
    assert record_edits.project_specs(project)==maps


def test_mixed_portable_params_and_raw_text_roll_back_together_and_retry(tmp_path,monkeypatch):
    game,project,params,maps=setup(tmp_path)
    changed=ItemDocument(params);changed.edit('EquipParamGoods',100,'sellValue',12)
    specs={**maps,RELATIVE:record_edits.create(RELATIVE,params,changed.export())}
    records=project/record_edits.FILENAME;records.write_bytes(record_edits.encode(specs))
    names=make_text_archive(names={'EquipParamGoods':{100:'Original'}})
    for root in (game,project):
        (root/texts.RELATIVE).parent.mkdir(parents=True,exist_ok=True)
        (root/texts.RELATIVE).write_bytes(names)
    store=ItemStore(game,project,False)
    store.edit('EquipParamGoods',100,'sellValue',17)
    store.rename('EquipParamGoods',100,'Changed name')
    before={path:path.read_bytes() for path in (records,project/texts.RELATIVE)}
    real=plugin_files.atomic_write
    failed=False
    def fail_after_records(path,data):
        nonlocal failed
        real(path,data)
        if path==records and not failed:
            failed=True
            raise OSError('interrupted after record write')
    with monkeypatch.context() as patch:
        patch.setattr(plugin_files,'atomic_write',fail_after_records)
        with pytest.raises(OSError,match='interrupted'):store.save()
    assert all(path.read_bytes()==raw for path,raw in before.items())
    assert store.get().dirty_count and not (project/RELATIVE).exists()
    store.save()
    again=ItemStore(game,project,False)
    assert again.get().value('EquipParamGoods',100,'sellValue')==17
    assert again.get().display_name('EquipParamGoods',100)=='Changed name'
    assert texts.RELATIVE not in record_edits.project_specs(project)
    assert record_edits.project_specs(project)[MAP]==maps[MAP]
    assert (game/RELATIVE).read_bytes()==params and (game/texts.RELATIVE).read_bytes()==names
