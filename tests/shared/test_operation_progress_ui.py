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

