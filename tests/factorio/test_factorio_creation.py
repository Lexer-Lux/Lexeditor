"""Created prototypes stay separate from imported source and survive export."""
import copy
import json
import shutil
from pathlib import Path

import pytest

from plugins.factorio.model import PrototypeStore, FactorioDataError, render_data_final_fixes

FIXTURE=Path(__file__).parent/'fixtures'


@pytest.mark.parametrize('kind', ['items','recipes','machines','technologies'])
def test_create_save_reload_discard_and_export(tmp_path, kind):
    project=tmp_path/'project'
    shutil.copytree(FIXTURE,project)
    source=(project/'source/data-raw-dump.json').read_bytes()
    store=PrototypeStore.from_project(project)
    original=copy.deepcopy(store.raw)
    template=sorted(store.names(kind))[0]
    store.create(kind,'my-new-prototype',template)
    row=next(r for r in store.rows(kind) if r['name']=='my-new-prototype')
    assert row['created'] and row['modified']
    assert store.raw==original
    store.save(project)
    loaded=PrototypeStore.from_project(project)
    assert 'my-new-prototype' in loaded.names(kind)
    script=render_data_final_fixes(loaded)
    assert 'table.deepcopy(source)' in script and 'data:extend({created})' in script
    assert 'created.name = "my-new-prototype"' in script
    assert (project/'source/data-raw-dump.json').read_bytes()==source
    loaded.discard(kind,'my-new-prototype')
    assert 'my-new-prototype' not in loaded.names(kind)


def test_creation_rejects_collisions_and_bad_templates_without_mutation():
    store=PrototypeStore(json.loads((FIXTURE/'source/data-raw-dump.json').read_text()))
    before=copy.deepcopy(store.overrides)
    for name, template in [('iron-gear-wheel','iron-gear-wheel'),('bad name','iron-gear-wheel'),('new-recipe','missing')]:
        with pytest.raises(FactorioDataError):
            store.create('recipes',name,template)
        assert store.overrides==before


def test_copy_keeps_current_edits_and_exports_registration_before_overrides():
    store=PrototypeStore(json.loads((FIXTURE/'source/data-raw-dump.json').read_text()))
    store.set_edit('recipes','iron-gear-wheel',{'energy_required':2})
    store.create('recipes','custom-gear','iron-gear-wheel')
    row=next(r for r in store.rows('recipes') if r['name']=='custom-gear')
    assert row['energyRequired']==2
    script=render_data_final_fixes(store)
    assert script.index('data:extend({created})')<script.index('p.energy_required = 2')
    store.discard()
    assert 'custom-gear' not in store.names('recipes')
    assert store.overrides=={'format':1,'edits':{}}
