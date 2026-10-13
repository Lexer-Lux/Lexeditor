"""Reference refresh and reset must retain the source control's write protection."""
import pytest
from playwright.sync_api import expect
from test_shared_ui_feedback import page, framework


@pytest.mark.parametrize('lock',['disabled','readonly','explicit'])
def test_reference_refresh_retains_lock_and_unlocks_explicitly(page,lock):
    framework(page)
    page.evaluate('''lock=>{
      const U=LexeditorUI;window.referenceWrites=[];window.referenceLocked=true;
      window.referenceInput=U.el('input',{type:'number',value:'2',disabled:lock==='disabled',readonly:lock==='readonly'});
      window.referenceRoot=U.provenanceControl({control:referenceInput,current:2,vanilla:1,
        readOnly:()=>lock==='explicit'&&referenceLocked,apply:value=>referenceWrites.push(value)});
      document.querySelector('main').append(referenceRoot);
    }''',lock)
    button=page.locator('.lex-reference-value')
    expect(button).to_be_disabled()
    page.evaluate('LexeditorUI.refreshReferences()')
    expect(button).to_be_disabled()
    page.evaluate("referenceInput.dispatchEvent(new Event('input',{bubbles:true}))")
    expect(button).to_be_disabled()
    button.evaluate("b=>b.dispatchEvent(new MouseEvent('click',{bubbles:true}))")
    page.evaluate('referenceRoot.lexRevert()')
    assert page.evaluate('referenceWrites')==[]
    page.evaluate("()=>{referenceLocked=false;referenceInput.disabled=false;referenceInput.removeAttribute('readonly');referenceRoot.refreshReference()}")
    expect(button).to_be_enabled()
    button.click()
    assert page.evaluate('referenceWrites')==[1]
