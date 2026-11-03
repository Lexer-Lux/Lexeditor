"""Beside-layout sections start their content level with plain sections.

A section whose content opens with a portrait-beside-fields layout must not
sit lower than its neighbor: the beside box is a column layout, not a padded
container, so it carries no vertical padding of its own.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1200, "height": 800})
        page.route("http://fixture/", lambda route: route.fulfill(
            content_type="text/html", body='<body><main style="width:1100px"></main></body>'))
        page.goto("http://fixture/")
        page.add_style_tag(content=(ROOT / "ui/framework.css").read_text(encoding="utf-8"))
        page.add_script_tag(content=(ROOT / "ui/framework.js").read_text(encoding="utf-8"))
        tops = page.evaluate("""() => {
          const {el, detailField, detailSection} = LexeditorUI;
          const field = label => detailField({label, control: el('input', {type: 'text', value: 'x'})});
          const row = el('div', {style: 'display:flex;gap:10px;'},
            detailSection({title: 'DATA', body: [
              el('div', {class: 'lex-detail-panel-beside'}, field('Portrait'), el('div', {}, field('Melee?'))),
            ]}),
            detailSection({title: 'COST', body: [field('Price')]}));
          row.querySelectorAll(':scope > .lex-detail-section').forEach(s => { s.style.flex = '1 1 0'; });
          document.querySelector('main').replaceChildren(row);
          const first = section => section.querySelector(
            ':scope > .lex-detail-section-content input').getBoundingClientRect().top;
          const sections = [...document.querySelectorAll('.lex-detail-section')];
          return sections.map(first);
        }""")
        browser.close()
    assert abs(tops[0] - tops[1]) <= 1, tops
    print(f"Beside and plain sections start level ({tops[0]}px vs {tops[1]}px).")


if __name__ == "__main__":
    main()
