"""Shared Add copies a real XML record without dropping nested mod fields."""
from pathlib import Path
import os
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(Path(__file__).resolve().parent))
sys.path.insert(0,str(ROOT/'tests/shared'))
from test_shared_ui_feedback import page, framework
from test_bannerlord_moduledata import ITEMS
from plugins.bannerlord.module_xml_data import read_document, save_document


def test_shared_add_creates_xml_record(page,tmp_path):
    source=tmp_path/'ModuleData/items.xml'
    source.parent.mkdir()
    source.write_text(ITEMS,encoding='utf-8')
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    def save(route):
        body=route.request.post_data_json
        try:
            result=save_document(tmp_path,body['path'],body['edits'],source_hash=body['sourceHash'])
            route.fulfill(json=result)
        except Exception as error:
            route.fulfill(status=400,json={'error':str(error)})
    page.route('http://fixture/api/module-data/save',save)
    framework(page)
    for script in ['editor_core.js','editor_shared.js','editor_moduledata.js']:
        page.add_script_tag(path=str(ROOT/'plugins/bannerlord'/script))
    page.add_script_tag(content='const shell={refresh(){}};function render(){renderModuleData()}')
    data=read_document(tmp_path,'ModuleData/items.xml')
    page.evaluate('''data=>{state.moduleDataFiles=['ModuleData/items.xml'];state.moduleDataView='records';
      state.moduleData=prepareModuleData(data);state.savedModuleData=clone(data);
      applyModuleDataRecordSelection(data.records[0]);renderModuleData()}''',data)
    page.locator('.lex-table-add').click(force=True)
    page.get_by_label('New record ID',exact=True).fill('new_torch')
    if destination:=os.environ.get('LEXEDITOR_UI_SCREENSHOT_DIR'):
        Path(destination).mkdir(parents=True,exist_ok=True)
        page.screenshot(path=str(Path(destination)/'bannerlord-create-record.png'))
    page.get_by_role('button',name='Create record',exact=True).click()
    page.wait_for_function("state.moduleData.records.some(r=>r.id==='new_torch')")
    after=read_document(tmp_path,'ModuleData/items.xml')
    assert [row['id'] for row in after['records']]==['torch','new_torch','peasant_maul_t1']
    assert source.read_text().count('UnknownFlag="keep"')==2
    assert page.evaluate("state.moduleData.records.find(r=>r.path===state.moduleDataRecordPath).id")=='new_torch'
    assert not errors,errors
