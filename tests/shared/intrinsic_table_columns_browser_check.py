"""Keep intrinsic numeric columns valid after fitting their headings."""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1600, "height": 1000})
    page.route('http://fixture/', lambda route: route.fulfill(
        content_type='text/html', body='<main style="width:900px;height:850px"></main>'))
    page.goto('http://fixture/')
    page.add_style_tag(content=(ROOT/'ui/framework.css').read_text(encoding='utf-8'))
    page.add_script_tag(content=(ROOT/'ui/framework.js').read_text(encoding='utf-8'))
    for template in [None, 'minmax(min-content,max-content) minmax(0,2fr) minmax(min-content,max-content) minmax(max(80px, 5rem),1fr)']:
        page.evaluate("""template => {
            const U=LexeditorUI;
            document.querySelector('main').replaceChildren(U.columnList({
                rows:Array.from({length:40},(_,id)=>({id,name:'Potion '+id,power:5,calc:'Static damage (Power × 20)'})),
                template, columns:[{key:'id',label:'ID',numeric:true},
                    {key:'name',label:'Name',grow:2},
                    {key:'power',label:'PWR',numeric:true},
                    {key:'calc',label:'CALC',grow:1}]
            }));
        }""", template)
        page.wait_for_timeout(150)
        result = page.evaluate("""() => {
            const table=document.querySelector('.lex-column-list');
            const cells=[...table.querySelector('.lex-column-list-header').children];
            const boxes=cells.map(e=>e.getBoundingClientRect());
            const row=[...table.querySelector('.lex-column-list-row').children].map(e=>e.getBoundingClientRect());
            return {valid:CSS.supports('grid-template-columns',table.style.getPropertyValue('--lex-column-list-template')),
                aligned:boxes.every((box,i)=>Math.abs(box.x-row[i].x)<1),
                distinct:boxes.every((box,i)=>!i || box.x>=boxes[i-1].right-1),
                level:boxes.every(box=>Math.abs(box.y-boxes[0].y)<1)};
        }""")
        assert all(result.values()), result
    browser.close()
print('Intrinsic and nested column sizes remain valid; headers and rows align.')
