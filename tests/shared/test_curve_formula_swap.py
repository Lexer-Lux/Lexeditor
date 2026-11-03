"""Piecewise curves draw every segment's own equation; the probe never swaps.

curveEditor takes segments declared with their own formulas and draws each
on its own span. The single swapping equation is gone: moving the probe
across spans leaves every segment's formula in place. The probe callback
still reports each hovered x so the caller knows what is under it.
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
BUILD = """() => {
  const seen = [];
  const variables = [
    {label: 'T1', key: 't1', control: Object.assign(
      document.createElement('input'), {value: '0'})},
    {label: 'T2', key: 't2', control: Object.assign(
      document.createElement('input'), {value: '10'})},
  ];
  const editor = window.LexeditorUI.curveEditor({
    title: 'Pieces', domain: {min: 0, max: 10}, range: {min: 0, max: 10},
    variables, evaluate: x => x,
    segments: [
      {from: 0, to: 5, formula: window.LexeditorUI.mathFormula(
        'Y(x) = T1', {variables})},
      {from: 5, to: 10, formula: window.LexeditorUI.mathFormula(
        'Y(x) = T2', {variables})},
    ],
    onProbe: x => seen.push(x),
  });
  document.querySelector('main').append(editor);
  editor._seen = seen;
  return editor;
}"""


def open_page(play):
    browser = play.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 900, "height": 900})
    page.route("http://fixture/**",
               lambda r: r.fulfill(body="<html></html>", content_type="text/html"))
    page.goto("http://fixture/")
    css = (ROOT / "ui/framework.css").read_text(encoding="utf-8")
    page.set_content("<style>" + css + "</style><main></main>")
    page.add_script_tag(path=str(ROOT / "ui/framework.js"))
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.evaluate(BUILD)
    page.evaluate("()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")
    assert not errors, errors
    return browser, page, errors


def test_segments_draw_each_formula_on_its_span_and_never_swap():
    with sync_playwright() as play:
        browser, page, errors = open_page(play)
        try:
            follows = page.locator('.lex-curve-math-follow')
            assert follows.count() == 2
            assert follows.evaluate_all(
                'nodes=>nodes.map(n=>n.getAttribute("aria-label"))') == [
                'Y(x) = T1', 'Y(x) = T2']
            rows = page.locator('.lex-curve-formula-segment')
            assert rows.count() == 2
            assert rows.nth(0).evaluate(
                'n=>n.textContent.replace(/\\s+/g,"")') == 'Y(x)=T1'
            assert rows.nth(1).evaluate(
                'n=>n.textContent.replace(/\\s+/g,"")') == 'Y(x)=T2'
            # The first span names T1 and the second names T2, each linked to
            # its own drawer variable.
            assert page.locator(
                '.lex-curve-math-follow[data-segment="0"]'
                ' .lex-curve-variable-t1[data-curve-variable="t1"]').count() >= 1
            assert page.locator(
                '.lex-curve-math-follow[data-segment="1"]'
                ' .lex-curve-variable-t2[data-curve-variable="t2"]').count() >= 1
            # Moving the probe across both spans swaps nothing: both
            # equations stay where their spans drew them.
            box = page.locator('.lex-curve-plot svg').bounding_box()
            for fraction in (0.2, 0.5, 0.8):
                page.mouse.move(box['x'] + box['width'] * fraction,
                                box['y'] + box['height'] / 2)
                page.wait_for_timeout(150)
            assert follows.count() == 2
            assert follows.evaluate_all(
                'nodes=>nodes.map(n=>n.getAttribute("aria-label"))') == [
                'Y(x) = T1', 'Y(x) = T2']
            seen = page.evaluate(
                "document.querySelector('.lex-curve-editor')._seen")
            assert any(x <= 5 for x in seen), seen
            assert any(x > 5 for x in seen), seen
            assert not errors, errors
        finally:
            browser.close()


def test_on_probe_reports_hovered_x():
    with sync_playwright() as play:
        browser, page, errors = open_page(play)
        try:
            box = page.locator('.lex-curve-plot svg').bounding_box()
            page.mouse.move(box['x'] + box['width'] * 0.75,
                            box['y'] + box['height'] / 2)
            page.wait_for_timeout(300)
            seen = page.evaluate(
                "document.querySelector('.lex-curve-editor')._seen")
            assert seen, 'probe never reported'
            assert all(0 <= x <= 10 for x in seen), seen
            assert not errors, errors
        finally:
            browser.close()
