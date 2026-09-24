from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
with sync_playwright() as pw:
 b=pw.chromium.launch(headless=True);p=b.new_page();p.route('http://fixture/',lambda r:r.fulfill(body='<body><main></main></body>',content_type='text/html'));p.goto('http://fixture/')
 p.add_style_tag(content=(ROOT/'ui/framework.css').read_text(encoding='utf-8'));p.add_style_tag(content='main{height:650px}')
 p.add_script_tag(content=(ROOT/'ui/framework.js').read_text(encoding='utf-8'))
 p.evaluate("""()=>{const U=LexeditorUI;window.rows=[0,1,2,3].map(id=>({id,name:'Record '+id,power:id+1}));document.querySelector('main').append(U.pagedListDetail({rows,key:r=>r.id,selected:0,splitKey:'multi-test',pageSize:10,maxBarrels:1,master:({rows,selected,select})=>U.columnList({rows,key:r=>r.id,selected,select,columns:[{key:'name',label:'Name'}]}),detail:r=>U.detailPanel({title:r.name,body:U.detailField({label:'Power',control:U.el('input',{type:'number',value:r.power,oninput:e=>r.power=Number(e.target.value)})})})}));}""")
 p.locator('.lex-list-row[data-key="1"]').click(modifiers=['Control']);assert p.locator('.lex-list-row.selected').count()==2
 p.locator('.lex-list-row[data-key="3"]').click(modifiers=['Shift']);assert p.locator('.lex-list-row.selected').count()==3
 p.locator('.lex-detail-field input').fill('4');p.wait_for_timeout(50)
 assert p.evaluate('rows.map(r=>r.power)')==[1,4,4,4]
 p.locator('.lex-detail-field input').fill('25');p.wait_for_timeout(80)
 assert p.evaluate('rows.map(r=>r.power)')==[1,25,25,25]
 p.locator('.lex-list-row[data-key="2"]').click(modifiers=['Control']);assert p.locator('.lex-list-row.selected').count()==2
 p.locator('.lex-list-row[data-key="0"]').click();assert p.locator('.lex-list-row.selected').count()==1
 b.close()
print('Ctrl toggle, Shift range, plain reset and multi-record property editing passed.')
