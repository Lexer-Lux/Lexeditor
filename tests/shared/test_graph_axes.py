"""Graphs label both axes, title equations after the Y axis, help variables.

Guard for the Graphs section of the ux-design skill: every curveEditor names
its X and Y axes in player terms with units from the shared unit component,
each segment's equation rides the middle of its own span, and drawer
variables with help carry the shared question-mark bubble.
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]


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
    return browser, page, errors


def settle(page):
    page.evaluate("()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")
    page.wait_for_timeout(200)


def test_axes_carry_labels_and_shared_units():
    with sync_playwright() as play:
        browser, page, errors = open_page(play)
        try:
            page.evaluate("""() => document.querySelector('main').append(
              window.LexeditorUI.curveEditor({title: 'Scaling',
                domain: {min: 1, max: 99}, range: {min: 0, max: 100},
                xLabel: 'Stat', yLabel: 'Scaling', yUnit: '%',
                evaluate: x => x}))""")
            settle(page)
            assert not errors, errors
            x = page.locator('.lex-curve-axis-name-x')
            assert x.inner_text() == 'Stat', x.inner_text()
            y = page.locator('.lex-curve-axis-name-y')
            assert 'Scaling' in y.inner_text(), y.inner_text()
            unit = y.locator('.lex-unit')
            assert unit.count() == 1
            assert unit.inner_text() == '%'
            # The unit rides the shared component, not a bare suffix.
            assert y.locator('.lex-unit-field[data-lex-unit="%"]').count() == 1
            # Without labels the axes still name themselves.
            page.evaluate("""() => document.querySelector('main').append(
              window.LexeditorUI.curveEditor({title: 'HP',
                domain: {min: 1, max: 100}, range: {min: 0, max: 100},
                evaluate: x => x}))""")
            settle(page)
            names = page.locator('.lex-curve-editor').nth(1).locator(
                '.lex-curve-axis-name')
            assert names.nth(0).inner_text() == 'LEVEL'
            assert names.nth(1).inner_text() == 'HP'
            assert not errors, errors
        finally:
            browser.close()


def test_segment_equations_center_on_their_spans():
    with sync_playwright() as play:
        browser, page, errors = open_page(play)
        try:
            page.evaluate("""() => {
              const variables = ['T1', 'T2', 'T3'].map(label => ({label,
                control: Object.assign(document.createElement('input'),
                  {value: '1'})}));
              document.querySelector('main').append(
                window.LexeditorUI.curveEditor({title: 'Pieces',
                  domain: {min: 0, max: 30}, range: {min: 0, max: 30},
                  variables, evaluate: x => x,
                  segments: [0, 1, 2].map(i => ({from: i * 10, to: i * 10 + 10,
                    formula: window.LexeditorUI.mathFormula(
                      `Y(x) = T${i + 1}`, {variables})}))}));
            }""")
            settle(page)
            assert not errors, errors
            follows = page.locator('.lex-curve-math-follow')
            assert follows.count() == 3
            centers = page.evaluate("""() => {
              const plot = document.querySelector('.lex-curve-plot')
                .getBoundingClientRect();
              return [...document.querySelectorAll('.lex-curve-math-follow')]
                .map(node => {
                  const atoms = [...node.querySelectorAll(
                    '.lex-curve-math-atom')];
                  const boxes = atoms.map(atom =>
                    atom.getBoundingClientRect());
                  const left = Math.min(...boxes.map(box => box.left));
                  const right = Math.max(...boxes.map(box => box.right));
                  return (left + right) / 2 - plot.left;
                }).map(center => center /
                  document.querySelector('.lex-curve-plot')
                    .getBoundingClientRect().width);
            }""")
            assert len(centers) == 3, centers
            assert centers[0] < centers[1] < centers[2], centers
            for center, expected in zip(centers, (1 / 6, 1 / 2, 5 / 6)):
                assert abs(center - expected) < 0.15, centers
            assert not errors, errors
        finally:
            browser.close()


def test_text_segments_ride_their_spans():
    with sync_playwright() as play:
        browser, page, errors = open_page(play)
        try:
            page.evaluate("""() => document.querySelector('main').append(
              window.LexeditorUI.curveEditor({title: 'Pieces',
                domain: {min: 0, max: 10}, range: {min: 0, max: 10},
                evaluate: x => x,
                segments: [
                  {from: 0, to: 5, formula: 'Y(x) = A'},
                  {from: 5, to: 10, formula: 'Y(x) = B'},
                ]}))""")
            settle(page)
            assert not errors, errors
            texts = page.locator('.lex-curve-editor .lex-curve-path-formula'
                                  ':not([style*="display: none"])')
            assert texts.count() == 2
            assert texts.nth(0).evaluate(
                'n=>n.textContent') == 'Y(x) = A'
            assert texts.nth(1).evaluate(
                'n=>n.textContent') == 'Y(x) = B'
            offsets = page.evaluate(
                '()=>[...document.querySelectorAll(".lex-curve-editor'
                ' .lex-curve-path-formula textPath")]'
                '.map(n=>parseFloat(n.getAttribute("startOffset")))')
            assert len(offsets) == 2, offsets
            assert offsets[0] < offsets[1], offsets
            assert abs(offsets[0] - 25) < 12, offsets
            assert abs(offsets[1] - 75) < 12, offsets
            assert not errors, errors
        finally:
            browser.close()


def test_drawer_variables_render_help_bubbles():
    with sync_playwright() as play:
        browser, page, errors = open_page(play)
        try:
            page.evaluate("""() => document.querySelector('main').append(
              window.LexeditorUI.curveEditor({title: 'Helped',
                domain: {min: 1, max: 100}, range: {min: 0, max: 100},
                evaluate: x => x,
                variables: [
                  {label: 'A', help: 'What A does.',
                   control: Object.assign(document.createElement('input'),
                     {value: '1'})},
                  {label: 'B',
                   control: Object.assign(document.createElement('input'),
                     {value: '1'})},
                ]}))""")
            settle(page)
            assert not errors, errors
            helped = page.locator(
                '.lex-curve-variable[data-curve-variable="a"] .lex-info-help')
            assert helped.count() == 1
            box = helped.bounding_box()
            assert (round(box['width']), round(box['height'])) == (16, 16), box
            assert page.locator(
                '.lex-curve-variable[data-curve-variable="b"] .lex-info-help'
            ).count() == 0
            page.locator('.lex-curve-editor').hover()
            helped.hover()
            assert page.get_by_role('tooltip').inner_text() == 'What A does.'
            assert not errors, errors
        finally:
            browser.close()
