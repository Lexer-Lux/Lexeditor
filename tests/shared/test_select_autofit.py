"""Dropdown faces scale down instead of clipping to an ellipsis.

Native selects cannot wrap: a long choice in a narrow box showed its first
words and an ellipsis. The control sweep fits every select's face to its
box, like number boxes.
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]


def test_long_choice_scales_to_its_box():
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 800, "height": 600})
            page.route("http://fixture/**", lambda r: r.fulfill(body="<html></html>", content_type="text/html"))
            page.goto("http://fixture/")
            css = (ROOT / "ui/framework.css").read_text(encoding="utf-8")
            page.set_content("<style>" + css + "</style><main></main>")
            page.add_script_tag(path=str(ROOT / "ui/framework.js"))
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.evaluate("""() => {
              const host = document.createElement('div');
              host.style.width = '220px';
              host.style.fontSize = '16px';
              host.innerHTML = `<select aria-label="Pick" style="width:100%"><option>A long choice label for scaling</option></select>`;
              document.querySelector('main').append(host);
            }""")
            page.evaluate("()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(()=>requestAnimationFrame(r))))")
            assert not errors, errors
            fit = page.evaluate("""() => {
              const select = document.querySelector('select');
              const style = getComputedStyle(select);
              const canvas = document.createElement('canvas');
              const context = canvas.getContext('2d');
              context.font = `${style.fontStyle} ${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
              const text = context.measureText(select.selectedOptions[0].textContent).width;
              const padding = parseFloat(style.paddingLeft) + parseFloat(style.paddingRight);
              return {size: parseFloat(style.fontSize),
                      fits: text <= select.clientWidth - padding - 22 + 1};
            }""")
            assert fit["size"] < 16, fit
            assert fit["fits"], fit
        finally:
            browser.close()
