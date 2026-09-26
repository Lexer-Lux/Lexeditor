"""Unknown kernel choices stay visible but cannot alter protected bytes."""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from plugins.ff8 import formats

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'shared'))
from test_shared_ui_feedback import page, framework, ROOT


def test_unknown_bits_preserved_and_unknown_choices_rejected(tmp_path):
    section=formats.SECTIONS[2]
    fields={f['name']:f for f in formats._public_fields(2)}
    flags=fields['target_info']
    entries=formats._lookup_payload(flags)['entries']
    protected=next(int(e.get('mask',e.get('value'))) for e in entries if e['readonly'])
    known=next(int(e.get('mask',e.get('value'))) for e in entries if not e['readonly'])
    raw=bytearray(512+section['number_sub_section']*section['sub_section_size'])
    raw[8:12]=(512).to_bytes(4,'little')
    start=512+int(flags['offset'])
    raw[start]=protected
    path=tmp_path/'kernel.bin'
    path.write_bytes(raw)
    with patch.object(formats,'source_path',return_value=path),patch.object(formats,'output_path',return_value=path):
        formats.save_kernel(2,[{'id':0,'field':'target_info','value':protected|known}])
        assert path.read_bytes()[start]==protected|known
        before=path.read_bytes()
        for value in [known, protected|known|128]:
            with pytest.raises(ValueError,match='read-only'):
                formats.save_kernel(2,[{'id':0,'field':'target_info','value':value}])
            assert path.read_bytes()==before
        choices=formats._lookup_payload(fields['attack_type'])['entries']
        unknown=next(e['value'] for e in choices if e['readonly'])
        with pytest.raises(ValueError,match='documented option'):
            formats.save_kernel(2,[{'id':0,'field':'attack_type','value':unknown}])
        assert path.read_bytes()==before


def test_readonly_fields_flags_and_lazy_enum_options(page):
    framework(page)
    for name in ['core.js','records.js','party.js']:
        page.add_script_tag(path=str(ROOT/'plugins/ff8'/name))
    enum=formats._lookup_payload({'lookup':'attack_type'})
    page.evaluate('''lookup=>{
      const m=document.querySelector('main');
      m.append(fieldControl({label:'Protected scalar',value:7,readonly:true}),
        fieldControl({label:'Attack type',value:0,lookup}),
        fieldControl({label:'Flags',value:2,lookup:{type:'flags',entries:[
          {value:1,name:'Known'},{value:2,name:'Unknown',readonly:true}]}}));
    }''',enum)
    assert page.get_by_label('Protected scalar').is_disabled()
    assert page.get_by_role('checkbox',name='Unknown',exact=True).is_disabled()
    assert page.get_by_role('checkbox',name='Unknown',exact=True).is_checked()
    assert page.get_by_role('checkbox',name='Known',exact=True).is_enabled()
    select=page.locator('select')
    select.focus()
    assert select.locator('option').filter(has_text='Unknown').count()>0
    assert select.locator('option').filter(has_text='Unknown').evaluate_all('es=>es.every(e=>e.disabled)')
