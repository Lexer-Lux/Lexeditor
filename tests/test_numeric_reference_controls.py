"""Numeric edits and reference restores keep bounds, data and usable space."""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]


def test_ff8_numeric_bounds_percentages_and_reference_restore():
    source=(ROOT/'plugins/ff8/core.js').read_text(encoding='utf-8')
    controls=source[source.index('  function numberControl('):source.index('  // A long list')]
    with sync_playwright() as play:
        browser=play.chromium.launch(headless=True)
        try:
            page=browser.new_page()
            page.route('http://fixture/**',lambda r:r.fulfill(body='<main></main>',content_type='text/html'))
            page.goto('http://fixture/')
            page.add_style_tag(path=str(ROOT/'ui/framework.css'))
            page.add_script_tag(path=str(ROOT/'ui/framework.js'))
            page.add_script_tag(content='''
              const {el,formatNumber,unitField}=LexeditorUI,shell={refresh(){}};
              let amount=50000,hit=128;
            '''+controls)
            page.evaluate('''() => {
              const U=LexeditorUI,input=numberControl(amount,0,65535,1,value=>amount=value,{'aria-label':'Amount'});
              const source=U.provenanceControl({control:U.unitField(input,'G'),current:()=>amount,
                vanilla:50000,internal:true,apply:value=>{amount=value;input.value=String(value)}});
              const field=U.detailField({label:'Amount',control:source});
              document.querySelector('main').append(field,ratio255Control(hit,value=>hit=value));
            }''')
            page.wait_for_timeout(150)
            amount=page.get_by_role('textbox',name='Amount',exact=True)
            amount.fill('65000')
            assert page.evaluate('amount')==65000,amount.input_value()
            amount.press('ArrowUp')
            assert page.evaluate('amount')==65001,amount.input_value()
            amount.blur()
            assert page.evaluate('amount')==65001
            amount.click(button='right')
            assert page.evaluate('amount')==50000
            assert amount.input_value().replace(',','')=='50000'
            exact=page.get_by_role('spinbutton',name='Hit rate out of 255',exact=True)
            exact.fill('255')
            assert page.evaluate('hit')==255
            assert page.get_by_role('spinbutton',name='Hit rate percentage',exact=True).input_value()=='100'
            exact.fill('256')
            assert exact.input_value()=='255' and page.evaluate('hit')==255
            # A matching reference must not reserve a hidden wide label inside
            # a narrow numeric control and erase the editable value.
            page.locator('.lex-source-control').evaluate("n=>n.style.width='150px'")
            assert amount.evaluate('n=>n.clientWidth-parseFloat(getComputedStyle(n).paddingLeft)-parseFloat(getComputedStyle(n).paddingRight)')>60
        finally:
            browser.close()


def test_rdr_reference_restore_works_outside_a_table_cell():
    source=(ROOT/'plugins/rdr2/core.js').read_text(encoding='utf-8')
    ref=source[source.index('function refField('):source.index('function multiValueReferenceStack(')]
    apply=source[source.index('function applyToInput('):source.index('function applyToControl(')]
    with sync_playwright() as play:
        browser=play.chromium.launch(headless=True)
        try:
            page=browser.new_page()
            page.route('http://fixture/**',lambda r:r.fulfill(body='<main></main>',content_type='text/html'))
            page.goto('http://fixture/')
            page.add_script_tag(path=str(ROOT/'ui/framework.js'))
            page.add_script_tag(content="const state={ds:'mine'};let restored=null;"+ref+apply)
            page.evaluate('''() => {
              const U=LexeditorUI,input=U.el('input',{type:'number',value:12,onchange:e=>restored=Number(e.target.value)});
              const source=refField(input,[['V','vtag',50]],12,(value,event)=>applyToInput(event,value));
              document.querySelector('main').append(U.detailField({label:'Price',control:source}));
              source.lexRevert(new MouseEvent('contextmenu'));
            }''')
            assert page.evaluate('restored')==50
            assert page.locator('input').input_value()=='50'
        finally:
            browser.close()


def test_ff8_select_preserves_named_views_and_numeric_record_ids():
    source=(ROOT/'plugins/ff8/core.js').read_text(encoding='utf-8')
    control=source[source.index('  function selectControl('):source.index('  function openItem(')]
    with sync_playwright() as play:
        browser=play.chromium.launch(headless=True)
        try:
            page=browser.new_page()
            page.route('http://fixture/**',lambda r:r.fulfill(body='<main></main>',content_type='text/html'))
            page.goto('http://fixture/')
            page.add_script_tag(path=str(ROOT/'ui/framework.js'))
            page.add_script_tag(content='const {el,lazyOptions,autoFitControlText}=LexeditorUI,shell={refresh(){}};let picked=null;'+control)
            page.evaluate("document.querySelector('main').append(selectControl('drawPoints',[{id:'map',name:'Map'},{id:'drawPoints',name:'Draw Points'}],value=>picked=value))")
            assert page.locator('select').input_value()=='drawPoints'
            page.locator('select').select_option('map')
            assert page.evaluate('picked')=='map'
            page.evaluate("document.querySelector('main').replaceChildren(selectControl(30,Array.from({length:50},(_,id)=>({id,name:'Record '+id})),value=>picked=value))")
            assert page.locator('select').input_value()=='30'
            page.locator('select').focus()
            page.locator('select').select_option('42')
            assert page.evaluate('picked')==42
        finally:
            browser.close()
