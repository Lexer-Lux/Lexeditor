"""The FF8 Tweaks tab reads dimmer than its neighbours, but not black.

The tab was once barely a different shade (luminance ratio 1.55) and a later
attempt went comically dark. The middle value holds a normal-to-Tweaks
luminance ratio near 2.5; this check screenshots the real stylesheets and
fails outside the 1.9-3.2 band.
"""
import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright
from PIL import Image

RATIO_FLOOR, RATIO_CEILING = 1.9, 3.2
TWEAKS_LUMINANCE_FLOOR = 0.03

HTML = ("<body data-lex-plugin='ff8'><header class='lex-shell-header'>"
        "<div class='lex-nav-frame'><nav></nav></div></header></body>")
BUILD = """() => {
  document.querySelector('nav').innerHTML = ['ITEMS', 'REFINE', 'TWEAKS'].map(label =>
    `<button class='${label === 'TWEAKS' ? 'lex-settings-tab lex-tweaks-tab' : ''}'>`
    + `<span class='lex-tab-label'><span class='lex-tab-label-text'>${label}</span></span></button>`).join('');
}"""


def luminance(rgb):
    def channel(value):
        value /= 255
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4
    red, green, blue = (channel(value) for value in rgb)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def tab_luminance(image, box):
    # Near the top edge, away from the label ink.
    points = [box["x"] + box["width"] * fraction for fraction in (0.04, 0.5, 0.96)]
    return sum(luminance(image.getpixel((int(x), int(box["y"] + 5)))) for x in points) / 3


def main():
    css = (ROOT / "plugins/ff8/editor.css").read_text(encoding="utf-8")
    css = re.sub(r'url\("/assets/ff8-menu\.ttf\?v=4"\)', "none", css)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 300})
        page.route("http://fixture/", lambda r: r.fulfill(content_type="text/html", body=HTML))
        page.goto("http://fixture/")
        page.add_style_tag(content=(ROOT / "ui/framework.css").read_text(encoding="utf-8"))
        page.add_style_tag(content=css)
        page.evaluate(BUILD)
        page.wait_for_timeout(200)
        boxes = page.evaluate(
            """() => [...document.querySelectorAll('nav button')].map(button => {
              const rect = button.getBoundingClientRect();
              return {label: button.textContent, x: rect.x, y: rect.y,
                      width: rect.width, height: rect.height};
            })""")
        image = Image.open(io.BytesIO(page.screenshot())).convert("RGB")
        browser.close()
    plain = [tab_luminance(image, box) for box in boxes if box["label"] != "TWEAKS"]
    tweaks = tab_luminance(image, next(box for box in boxes if box["label"] == "TWEAKS"))
    normal = sum(plain) / len(plain)
    ratio = normal / tweaks
    assert abs(plain[0] - plain[1]) < 0.01, f"neighbour tabs disagree: {plain}"
    assert tweaks >= TWEAKS_LUMINANCE_FLOOR, f"Tweaks tab is comically dark: {tweaks:.4f}"
    assert RATIO_FLOOR <= ratio <= RATIO_CEILING, f"Tweaks shade ratio {ratio:.2f} outside 1.9-3.2"
    print(f"Tweaks tab shade: normal {normal:.4f} vs Tweaks {tweaks:.4f}, ratio {ratio:.2f}.")


if __name__ == "__main__":
    main()
