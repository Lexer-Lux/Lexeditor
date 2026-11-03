"""Live activity updates the shared busy UI without hiding operation errors."""
from test_shared_ui_feedback import framework, page


def test_live_label_lock_and_late_response_cleanup(page, tmp_path):
    framework(page)
    page.evaluate('''()=>{
      const U=LexeditorUI,owner={};
      U.setEditorBusy(owner,'Saving changes');
      window.reads=0;window.tokens=[];
      window.job=U.observeOperation({
        run:id=>{tokens.push(id);return new Promise(resolve=>window.finish=resolve)},
        read:id=>{tokens.push(id);reads++;return reads===1
          ?Promise.resolve({running:true,label:'Building Estus Rework (2/3)'})
          :new Promise(resolve=>window.late=resolve)},
        progress:label=>U.setEditorBusy(owner,label),
      }).finally(()=>U.setEditorBusy(owner,null));
    }''')
    page.get_by_text('Building Estus Rework (2/3)', exact=True).wait_for()
    assert page.evaluate('document.body.inert')
    page.wait_for_function('typeof late==="function"')
    assert page.evaluate('new Set(tokens).size') == 1
    page.screenshot(path=str(tmp_path / 'building-stage.png'))
    page.evaluate('finish({saved:true});void 0')
    page.wait_for_function('!document.body.inert')
    page.evaluate('late({running:true,label:"Old operation"});void 0')
    page.wait_for_timeout(250)
    assert page.locator('.lex-editor-activity').count() == 0
    assert page.evaluate('reads') == 2


def test_status_failure_keeps_work_running_and_preserves_the_real_error(page):
    framework(page)
    page.evaluate('''()=>{
      const U=LexeditorUI,owner={};window.reads=0;
      U.setEditorBusy(owner,'Saving changes');
      U.observeOperation({run:()=>new Promise((_,reject)=>window.fail=reject),
        read:async()=>{reads++;throw Error('Status unavailable')},
        progress:label=>U.setEditorBusy(owner,label)
      }).catch(error=>window.operationError=error.message)
        .finally(()=>U.setEditorBusy(owner,null));
    }''')
    page.wait_for_function('reads>0')
    assert page.evaluate('document.body.inert')
    assert page.get_by_text('Saving changes', exact=True).is_visible()
    page.evaluate('fail(Error("Archive exceeds its size limit"));void 0')
    page.wait_for_function('!document.body.inert')
    assert page.evaluate('operationError') == 'Archive exceeds its size limit'


def test_long_operation_label_fits_narrow_window(page, tmp_path):
    page.set_viewport_size({'width': 360, 'height': 640})
    framework(page)
    label = 'Checking/building ' + 'LongModName' * 12 + ' (18/18)'
    page.evaluate('(label)=>LexeditorUI.setEditorBusy({},label)', label)
    activity = page.locator('.lex-editor-activity')
    assert activity.inner_text() == label
    assert activity.evaluate('''e=>{
      const r=e.getBoundingClientRect();
      return r.left>=8 && r.right<=innerWidth-8 &&
        r.top>=8 && r.bottom<=innerHeight-8 && e.scrollWidth<=e.clientWidth;
    }''')
    page.screenshot(path=str(tmp_path / 'long-operation-label.png'))

