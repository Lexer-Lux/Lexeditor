"""Embedded property pagers stretch their dealt columns across the pane."""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]


def test_paginated_detail_columns_keep_bounded_values_readable():
    with sync_playwright() as play:
        browser=play.chromium.launch(headless=True)
        try:
            page=browser.new_page(viewport={'width':1000,'height':700})
            page.route('http://fixture/**',lambda r:r.fulfill(body='<main id="main"></main>',content_type='text/html'))
            page.goto('http://fixture/')
            page.add_style_tag(path=str(ROOT/'ui/framework.css'))
            page.add_script_tag(path=str(ROOT/'ui/framework.js'))
            page.evaluate('''() => {
              const U=LexeditorUI;
              const host=document.querySelector('main');host.style.width='650px';host.style.height='450px';
              const fields=['Physical','Magic','Fire','Lightning'].map(label=>U.detailField({label,
                control:U.el('input',{type:'number',min:0,max:9999,value:9999,'aria-label':label})}));
              host.append(U.detailPanel({title:'Damage',paginate:{inline:true},body:[
                U.detailSection({title:'Base damage',body:fields}),
                U.detailSection({title:'References',body:[U.detailField({label:'Source',control:U.readonlyField('Behavior 212000100')})]})]}));
            }''')
            page.wait_for_timeout(400)
            assert page.locator('.lex-tweak-column').first.evaluate('n=>n.clientWidth/n.parentElement.clientWidth')>0.9
            assert page.get_by_role('spinbutton',name='Physical').evaluate('n=>n.clientWidth')>=70
            page.set_viewport_size({'width':900,'height':650});page.wait_for_timeout(300)
            assert page.get_by_role('spinbutton',name='Physical').input_value()=='9999'
        finally: browser.close()
