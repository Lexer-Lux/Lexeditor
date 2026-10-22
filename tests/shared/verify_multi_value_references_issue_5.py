from pathlib import Path
import re
from plugin_ui import plugin_ui
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
html = plugin_ui('rdr2')
framework = (ROOT/'ui/framework.js').read_text(encoding='utf-8')
css = (ROOT/'ui/framework.css').read_text(encoding='utf-8')

# One component owns membership/value comparison, per-entry reference stacks,
# and the reference-only ghost segment for all three requested fields.
assert "function multiValueReferences({" in html
assert "function multiValueReferenceStack(" in html
assert 'const ghosts=new Map()' in html
assert 'LexeditorUI.actionRow()' in html
assert 'LexeditorUI.stack({fill:false' in html
assert '"data-multi-ref-kind":kind' in html
assert 'kind:"item-effects"' in html
assert 'kind:"item-tags"' in html
assert 'kind:"challenge-rewards"' in html
stack_style = re.search(r'\.lex-badge\s*\{([^}]+)\}', css)
assert stack_style
font_size = re.search(r'font-size:([\d.]+)px', stack_style.group(1))
assert font_size and float(font_size.group(1)) >= 10
assert 'font:8.5px/1.3 Consolas,monospace' not in html

# The old field-level and index-based comparisons can report a green check for
# the wrong set. They must not return.
assert "tagsEqual(src.tags,current)" not in html
assert "vrank?.rewards?.[index]" not in html
assert 'class:"restore-ref"' not in html

# The established full selectors remain the only add paths. The shared New
# button derives its accessible name from this required title.
assert 'newButton({title:"Add effect"' in html
assert 'newButton({title:"Add catalog tag"' in html
assert "pickIdentifier(\"Add effect\"" in html
assert "pickCatalogTag(it" in html
assert "dl-effects" not in html
assert "dl-tags" not in html

functions=html[html.index('function multiValueReferenceStack('):html.index('// Carry rules are already one row per context.')]
with sync_playwright() as play:
    browser=play.chromium.launch(headless=True)
    try:
        page=browser.new_page()
        errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.route('http://fixture/',lambda route:route.fulfill(content_type='text/html',body='<main></main>'))
        page.goto('http://fixture/')
        page.add_style_tag(content=css)
        page.add_script_tag(content=framework)
        page.add_script_tag(content='const state={ds:"mine"};const el=LexeditorUI.el;'+functions)
        def render(dataset='mine',values=True):
            return page.evaluate('''({dataset,values})=>{
                state.ds=dataset;
                const current=[{key:'a',value:2},{key:'b',value:3}];
                // Reference order differs from the current order. Two sources
                // repeat c; it must be one ghost with both source comparisons.
                const references=[['V','',[{key:'b',value:8},{key:'a',value:2},{key:'c',value:4}]],
                    ['L','',[{key:'a',value:5},{key:'c',value:6},{key:'d',value:7}]]];
                const root=multiValueReferences({kind:'fixture',current,references,
                    keyOf:e=>e.key,entryValue:values?e=>e.value:undefined,
                    renderCurrent:e=>el('span',{},e.key),renderGhost:e=>el('span',{},'ghost '+e.key)});
                document.querySelector('main').replaceChildren(root);
                return [...root.querySelectorAll('[data-multi-ref-key]')].map(e=>({
                    key:e.dataset.multiRefKey,badges:[...e.querySelectorAll('.lex-badge')].map(b=>b.textContent)}));
            }''',{'dataset':dataset,'values':values})
        assert render()==[
            {'key':'a','badges':['V ✓','L: 5']},
            {'key':'b','badges':['V: 8','L ×']},
            {'key':'c','badges':['V: 4','L: 6']},
            {'key':'d','badges':['V ×','L: 7']},
        ]
        assert render(values=False)==[
            {'key':'a','badges':['V ✓','L ✓']},
            {'key':'b','badges':['V ✓','L ×']},
            {'key':'c','badges':['V ✓','L ✓']},
            {'key':'d','badges':['V ×','L ✓']},
        ]
        assert render(dataset='vanilla')==[
            {'key':'a','badges':[]},{'key':'b','badges':[]},
        ]
        assert not errors,errors
    finally:
        browser.close()
print("PASS: shared multi-value membership, keyed values, deduplicated ghosts and picker contracts")
