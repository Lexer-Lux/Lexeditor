"""A selected record must not change the saved panel split on the next resize."""
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('extra', ['', 'leadingPanel', 'trailingPanel'])
def test_selection_replacement_keeps_split_on_resize(extra):
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1200, "height": 800})
            page.route('http://fixture/**', lambda route: route.fulfill(
                body='<main id="main"></main>', content_type='text/html'))
            page.goto('http://fixture/')
            page.add_style_tag(path=str(ROOT / 'ui/framework.css'))
            page.add_script_tag(path=str(ROOT / 'ui/framework.js'))
            page.evaluate('''extra => {
                const UI=LexeditorUI;
                const rows=[{id:1,name:'First'},{id:2,name:'Second'}];
                const extraOptions = extra ? {[extra]:r=>UI.detailPanel({title:'Extra '+r.name})} : {};
                const view=UI.pagedListDetail({...extraOptions,rows,key:r=>r.id,selected:1,
                    defaultSplit:42,minLeft:280,minRight:360,
                    master:v=>UI.columnList({rows:v.rows,key:r=>r.id,selected:v.selected,
                        select:v.select,columns:[{key:'name',label:'Name'}]}),
                    detail:r=>UI.detailPanel({title:r.name,body:[UI.detailField({label:'Value',
                        control:UI.readonlyField(r.id)})]})});
                document.querySelector('main').append(view);
            }''', extra)
            page.wait_for_timeout(300)
            divider = page.locator('.lex-panel-layout-divider')
            original = [node.bounding_box()['x'] for node in divider.all()]
            page.locator('.lex-column-list-row').filter(has_text='Second').click()
            page.wait_for_timeout(200)
            for _ in range(3):
                page.set_viewport_size({'width': 1210, 'height': 800})
                page.wait_for_timeout(100)
                page.set_viewport_size({'width': 1200, 'height': 800})
                page.wait_for_timeout(100)
            assert all(abs(node.bounding_box()['x'] - old) < 1
                       for node, old in zip(divider.all(), original))
            titles = page.locator('.lex-detail-panel-title').all_inner_texts()
            assert 'Second' in titles
            if extra:
                assert 'Extra Second' in titles
        finally:
            browser.close()
