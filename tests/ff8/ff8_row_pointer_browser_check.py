"""FF8's hand cursor sits just left of the selected row's text, not at the column edge."""
# Dev caches and outputs live in the temp folder, never in the checkout.
DEV_CACHE = __import__("pathlib").Path(__import__("tempfile").gettempdir()) / "lexeditor-dev"
import re
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from plugin_ui import plugin_ui
SHOT = DEV_CACHE / "ff8_row_pointer.png"


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 900, "height": 300})
        page.route("http://fixture/", lambda r: r.fulfill(content_type="text/html",
                   body='<body data-lex-plugin="ff8"><main style="width:700px"></main></body>'))
        page.route("http://fixture/assets/icons/0.png", lambda r: r.fulfill(
            path=str(ROOT / "plugins/ff8/assets/icons/0.png")) if (ROOT / "plugins/ff8/assets/icons/0.png").is_file()
            else r.fulfill(status=404))
        page.goto("http://fixture/")
        page.add_style_tag(content=(ROOT / "ui/framework.css").read_text(encoding="utf-8"))
        page.add_style_tag(content=(ROOT / "plugins/ff8/editor.css").read_text(encoding="utf-8"))
        page.add_script_tag(content=(ROOT / "ui/framework.js").read_text(encoding="utf-8"))
        # The icon comes from the player's game data; mark where it would draw.
        page.add_style_tag(content=".lex-column-cell-content::before{outline:2px solid red}")
        results = {}
        for align in ("start", "center", "end"):
            page.evaluate("""align=>{
              document.querySelector('main').replaceChildren(LexeditorUI.columnList({
                rows:[{id:'#10',ability:'Elem-Atk-J'},{id:'#16',ability:'Elem-Defx4'}],key:r=>r.id,selected:'#16',
                class:'ff8-record-list',template:'70px minmax(200px,1fr)',
                columns:[{key:'id',label:'ID'},{key:'ability',label:'Junction abilities',align}]}));
            }""", align)
            page.wait_for_timeout(100)
            results[align] = page.evaluate("""()=>{
              const content=document.querySelector('.lex-list-row.selected .lex-column-pointer-cell .lex-column-cell-content');
              const range=document.createRange();range.selectNodeContents(content);
              const texts=[...range.getClientRects()].filter(r=>r.width>0);
              const before=getComputedStyle(content,'::before');
              const text=Math.min(...texts.map(r=>r.left));
              const handRight=content.getBoundingClientRect().left+parseFloat(before.left)+parseFloat(before.width);
              const handLeft=handRight-parseFloat(before.width);
              return {content:content.getBoundingClientRect().left,text,handLeft,handRight,position:before.position};
            }""")
        page.screenshot(path=str(SHOT))
        browser.close()
    for align, row in results.items():
        assert row["position"] == "absolute", row
        # The hand's right edge sits a few pixels left of the text, wherever the text is.
        assert 0 < row["text"] - row["handRight"] <= 10, (align, row)
    print("FF8 hand cursor sits beside the selected text:", results)


if __name__ == "__main__":
    main()
