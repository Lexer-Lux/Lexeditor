"""Headless regression check of signed FF8 curves in the shared SVG renderer."""
from pathlib import Path
import sys
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from plugin_ui import plugin_ui
# The curve lives in records.js, so the page and its modules are read together.
editor=plugin_ui('ff8')
curve=editor[editor.index('  const characterCurveOrder='):editor.index('  function characterCurveFormula(')]
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True)
 page=browser.new_page()
 page.route('http://lexeditor.test/**',lambda route:route.fulfill(body='<html><body></body></html>',content_type='text/html'))
 page.goto('http://lexeditor.test/')
 page.add_script_tag(path=str(ROOT/'ui/framework.js'))
 page.evaluate(curve+'''
window.fields=[0,2,0,1].map((value,i)=>({field:'vit_'+(i+1),value}));
window.graph=LexeditorUI.curveEditor({title:'VIT',domain:{min:1,max:100},range:()=>characterCurveRange('VIT',fields),evaluate:l=>characterCurveValue('VIT',fields,l,true)});
document.body.append(graph);
''')
 page.wait_for_timeout(100)
 assert page.locator('.lex-curve-axis-bottom').inner_text()=='-1,237'
 assert page.locator('.lex-curve-minimum').inner_text()=='-1,237'
 points=page.locator('.lex-curve-line').get_attribute('d')
 assert '160.00' in points
 # Negative bars extend down from zero, not up from the bottom of the graph.
 last=page.locator('.lex-curve-bars rect').last
 assert float(last.get_attribute('height'))>100
 assert float(last.get_attribute('y'))<40
 page.evaluate("fields[1].value=1;graph.dispatchEvent(new Event('input',{bubbles:true}))")
 page.wait_for_timeout(100)
 assert page.locator('.lex-curve-axis-bottom').inner_text()=='0'
 assert page.locator('.lex-curve-minimum').inner_text()=='0'
 assert page.locator('.lex-curve-maximum').inner_text()=='0'
 assert all(float(x)==0 for x in page.locator('.lex-curve-bars rect').evaluate_all("nodes=>nodes.map(n=>n.getAttribute('height'))"))
 browser.close()
print('Signed axis, negative bars, and live zero-preset redraw passed in headless Chromium')
