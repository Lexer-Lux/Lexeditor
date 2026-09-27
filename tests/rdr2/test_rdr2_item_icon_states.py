"""Inventory previews use accessible shared pending and missing states."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'shared'))
from test_shared_ui_feedback import page, framework


def test_inventory_preview_pending_missing_and_decoded_image(page):
    framework(page)
    source = (Path(__file__).resolve().parents[2] / 'plugins/rdr2/items.js').read_text(encoding='utf-8')
    source = source[source.index('function itemIcon('):source.index('function modelPreviewKey(')]
    page.add_script_tag(content='''
      const el=LexeditorUI.el, localizedValue=()=>"Test item";
      let finishIcon;
      const loadInventoryIcon=()=>new Promise(resolve=>{finishIcon=resolve;});
    ''' + source)
    for image in (None, 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24"><rect width="24" height="24" fill="red"/></svg>'):
        page.evaluate('''()=>document.querySelector('main').replaceChildren(
          itemIcon({dict:'inventory',id:'test'},{key:'test'}))''')
        assert page.get_by_role('status',name='Loading inventory icon',exact=True).count()==1
        page.evaluate('src=>finishIcon(src)',image)
        page.wait_for_function("!document.querySelector('main [aria-busy=true]')")
        if image:
            page.wait_for_function("document.querySelector('main img')?.naturalWidth===24")
            assert page.get_by_role('img',name='Test item icon',exact=True).count()==1
        else:
            assert page.get_by_role('img',name='Inventory icon is unavailable',exact=True).count()==1
            assert page.locator('main .lex-no-image').count()==1
            assert page.locator('main button, main [role=button]').count()==0
