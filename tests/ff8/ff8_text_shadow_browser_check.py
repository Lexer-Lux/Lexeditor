"""Themed text shadow reaches the FF8 inputs and the Lexeditor logo.

Chromium form controls never inherit text-shadow, and the FF8 input token
once held `inherit`, which resolves to guaranteed-invalid on :root and fell
back to `none`. Inputs now reference the theme token and the shared brand
button states it. Small chrome (help bubbles, badges, pager selects) keeps
its deliberate `none`.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright

THEMED = "rgb(37, 37, 37) 2px 2px 0px"

HTML = ("<body data-lex-plugin='ff8'>"
        "<button class='lex-brand-button'><h1 data-lex-brand-label='LEXEDITOR'></h1></button>"
        "<div class='lex-detail-field-control'><div class='lex-source-control'>"
        "<input type='number' value='42' id='ap'>"
        "<input type='text' value='Squall' id='name'>"
        "<select id='pick'><option>One</option></select>"
        "</div></div>"
        "<button class='lex-info-help' aria-label='help'>?</button>"
        "</body>")


def main():
    css = (ROOT / "plugins/ff8/editor.css").read_text(encoding="utf-8")
    css = re.sub(r'url\("/assets/ff8-menu\.ttf\?v=4"\)', "none", css)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.route("http://fixture/", lambda r: r.fulfill(content_type="text/html", body=HTML))
        page.goto("http://fixture/")
        page.add_style_tag(content=(ROOT / "ui/framework.css").read_text(encoding="utf-8"))
        page.add_style_tag(content=css)
        shadows = page.evaluate("""() => ({
          brand: getComputedStyle(document.querySelector('.lex-brand-button h1')).textShadow,
          number: getComputedStyle(document.querySelector('#ap')).textShadow,
          text: getComputedStyle(document.querySelector('#name')).textShadow,
          select: getComputedStyle(document.querySelector('#pick')).textShadow,
          help: getComputedStyle(document.querySelector('.lex-info-help')).textShadow,
        })""")
        browser.close()
    for key in ("brand", "number", "text", "select"):
        assert shadows[key] == THEMED, (key, shadows[key])
    assert shadows["help"] == "none", ("help bubble lost its reset", shadows["help"])
    print(f"FF8 themed shadow on brand, number, text and select ({THEMED}); chrome resets kept.")


if __name__ == "__main__":
    main()
