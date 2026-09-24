from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
with sync_playwright() as pw:
 b=pw.chromium.launch(headless=True);p=b.new_page()
 p.route('http://fixture/',lambda r:r.fulfill(body='<body></body>',content_type='text/html'));p.goto('http://fixture/')
 p.add_style_tag(content=(ROOT/'ui/framework.css').read_text(encoding='utf-8'));p.add_script_tag(content=(ROOT/'ui/framework.js').read_text(encoding='utf-8'))
 p.evaluate("""()=>{const U=LexeditorUI;window.before={magic:[{name:'Aero',power:22}],settings:{maxSpell:10}};window.after={magic:[{name:'Aero',power:30}],settings:{maxSpell:20}};window.count=2;
 document.body.append(U.settingsSaveControl({dirtyCount:()=>count,pendingChanges:()=>U.pendingChangeList(before,after),save:async()=>{count=0}}));}""")
 p.locator('.lex-settings-save-control').hover()
 tip=p.locator('.lex-save-preview');tip.wait_for()
 assert tip.locator('li').count()==2
 assert 'Aero' in tip.inner_text() and '22' in tip.inner_text() and '30' in tip.inner_text()
 p.keyboard.press('Escape');assert tip.count()==0
 p.mouse.move(0,400);p.locator('.lex-settings-save-control').hover();tip.wait_for()
 p.locator('.lex-settings-save-control').click();assert tip.count()==0
 b.close()
print('Save preview lists exact cross-record changes, supports Escape, and closes on save.')
