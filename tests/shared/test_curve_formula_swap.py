"""curveEditor formula swaps and probe callback.

Segment curves rename their own equation as the probe moves: the swap
rebuilds the line text, the overlay atoms and the bottom block, relinks
every token to its variable, and redraws. The probe callback reports
each hovered x so the caller knows which segment is under it.
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
BUILD = """() => {
  const seen = [];
  const editor = window.LexeditorUI.curveEditor({
    title: 'Swap', domain: {min: 0, max: 10}, range: {min: 0, max: 10},
    variables: [
      {label: 'T1', key: 't1', control: Object.assign(
        document.createElement('input'), {value: '0'})},
      {label: 'T2', key: 't2', control: Object.assign(
        document.createElement('input'), {value: '10'})},
    ],
    evaluate: x => x,
    formula: window.LexeditorUI.mathFormula('V(x) = T1 + T2', {variables: [
      {label: 'T1', key: 't1'}, {label: 'T2', key: 't2'}]}),
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


def test_refresh_formula_swaps_atoms_and_relinks():
    with sync_playwright() as play:
        browser, page, errors = open_page(play)
        try:
            before = page.evaluate(
                "document.querySelector('.lex-curve-formula').textContent")
            assert 'T1' in before and 'T2' in before
            page.evaluate("""() => document.querySelector('.lex-curve-editor')
              .refreshFormula(window.LexeditorUI.mathFormula('V(x) = T2', {variables: [
                {label: 'T1', key: 't1'}, {label: 'T2', key: 't2'}]}))""")
            after = page.evaluate(
                "document.querySelector('.lex-curve-formula').textContent")
            assert after.replace(' ', '') == 'V(x)=T2', after
            # The T1 token is gone with its link; the T2 token stays linked.
            page.hover('.lex-curve-editor')
            page.hover('.lex-curve-variable[data-curve-variable="t1"]')
            assert page.evaluate(
                "document.querySelectorAll('.lex-curve-variable-highlight').length") == 1
            page.hover('.lex-curve-variable[data-curve-variable="t2"]')
            assert page.evaluate(
                "document.querySelectorAll('.lex-curve-variable-highlight').length") > 1
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
