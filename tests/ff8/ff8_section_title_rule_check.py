"""The FF8 theme draws no rule under a section title.

Lexer: "i don't like how the headers have this line underneath them. remove."
The panel's own heading already had no rule; the section titles still drew a
1px line in the theme's border colour. This builds the same detail panel the
editor builds, in the real shared stylesheet and the plugin's own, and then
looks at the pixels: a rule under a title is a row of one flat colour across
the whole panel, which is what this looks for.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
SHOTS = Path(tempfile.gettempdir()) / "lexeditor-dev"
RULE = (146, 146, 146)


def flat_rule_rows(image: Image.Image, left: int, right: int, top: int, bottom: int) -> list[int]:
    """Rows between top and bottom that are one flat border colour throughout."""
    rows = []
    for y in range(top, bottom):
        values = [image.getpixel((x, y)) for x in range(left, right)]
        if values and all(value == RULE for value in values):
            rows.append(y)
    return rows


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.route("http://fixture/", lambda route: route.fulfill(
            content_type="text/html",
            body='<body data-lex-plugin="ff8"><main></main></body>'))
        page.goto("http://fixture/")
        page.add_style_tag(content=(ROOT / "ui" / "framework.css").read_text(encoding="utf-8"))
        page.add_style_tag(content=(ROOT / "plugins" / "ff8" / "editor.css").read_text(encoding="utf-8"))
        page.add_script_tag(content=(ROOT / "ui" / "framework.js").read_text(encoding="utf-8"))
        page.evaluate("""() => {
          const U = LexeditorUI;
          const panel = U.detailPanel({
            className: "lex-detail detail",
            title: "Sound 1",
            identity: U.el("span", {class: "lex-pinnable-property"}, U.recordId(1)),
            body: [
              U.detailSection({title: "SOUND", body: [
                U.detailField({label: "FORMAT", control: U.readonlyField("ADPCM")}),
                U.detailField({label: "LOOP", control: U.readonlyField("No")})]}),
              U.detailSection({title: "MOD FILES", body: [U.detailNote("No mod replaces this sound.")]}),
            ]});
          document.querySelector("main").append(panel);
        }""")
        page.wait_for_timeout(300)
        titles = page.locator(".lex-detail-section-title")
        count = titles.count()
        assert count == 2, count
        borders = page.evaluate("""() => [...document.querySelectorAll(".lex-detail-section-title")].map(node => {
          const style = getComputedStyle(node);
          const box = node.getBoundingClientRect();
          return {width: style.borderBottomWidth, style: style.borderBottomStyle,
                  colour: style.borderBottomColor, bottom: Math.round(box.bottom), left: Math.round(box.left),
                  right: Math.round(box.right)};
        })""")
        for border in borders:
            assert border["width"] in ("0px", ""), border
            assert border["style"] in ("none", ""), border
        box = page.locator(".lex-detail-section-title").first.bounding_box()
        shot = SHOTS / "ff8-section-titles.png"
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(shot))
        image = Image.open(shot).convert("RGB")
        left = int(box["x"]) + 4
        right = int(box["x"] + box["width"]) - 4
        top = int(box["y"]) - 6
        bottom = int(box["y"] + box["height"]) + 6
        rules = flat_rule_rows(image, left, right, max(0, top), min(image.height, bottom))
        assert not rules, f"a flat rule still runs under the title at rows {rules}, see {shot}"
        browser.close()
    print(f"FF8 section titles draw no rule: two titles measured, no flat border row within 6px "
          f"above or below either. Screenshot {shot}.")


if __name__ == "__main__":
    sys.exit(main())
