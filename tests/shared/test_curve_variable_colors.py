"""Curve formulas color their own variables and glow both ways.

A curve's variables decide which formula identifiers take a color:
FF8's A-D keep their letters, DS1's stages each own one key
(T1 never lights T2). Hovering a drawer variable
highlights its formula atoms over the plot and hovering an atom
lights the drawer. A formula without variables stays uncolored.
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
MOUNT = """() => {
  const main = document.querySelector('main');
  main.style.display = 'grid';
  main.style.gap = '24px';
  const input = () => {
    const box = document.createElement('input');
    box.value = '1';
    return box;
  };
  const ff8 = [
    {label: 'A', control: input()},
    {label: 'B', control: input()},
  ];
  main.append(LexeditorUI.curveEditor({
    title: 'FF8', domain: {min: 1, max: 100}, range: {min: 0, max: 9},
    evaluate: x => x,
    variables: ff8,
    formula: LexeditorUI.mathFormula('Y = A + 2 * B', {variables: ff8}),
  }));
  const ds1 = [
    {label: 'T1', key: 't1', control: input()},
    {label: 'T2', key: 't2', control: input()},
    {label: 'V1', key: 'v1', control: input()},
  ];
  main.append(LexeditorUI.curveEditor({
    title: 'DS1', domain: {min: 1, max: 9}, range: {min: 0, max: 9},
    evaluate: x => x,
    variables: ds1,
    formula: LexeditorUI.mathFormula('T1 + V1 = T2', {variables: ds1}),
  }));
  main.append(LexeditorUI.mathFormula('A + B'));
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
    page.evaluate(MOUNT)
    page.evaluate("()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")
    assert not errors, errors
    return browser, page, errors


def test_explicit_letters_color_formula_and_drawer():
    with sync_playwright() as play:
        browser, page, errors = open_page(play)
        try:
            first = page.locator(".lex-curve-editor").nth(0)
            assert first.locator(
                ".lex-curve-math-atom .lex-curve-variable-a").count() == 1
            assert first.locator(
                ".lex-curve-math-atom .lex-curve-variable-b").count() == 1
            color = page.evaluate(
                "() => getComputedStyle(document.querySelector("
                "'.lex-curve-editor .lex-curve-variable-name.lex-curve-variable-a')).color")
            assert color == "rgb(240, 91, 91)", color
            # Drawer -> formula atoms over the plot.
            first.hover()
            first.locator(
                ".lex-curve-variable[data-curve-variable='a']").hover()
            assert first.locator(
                ".lex-curve-math-atom .lex-curve-variable-a"
                ".lex-curve-variable-highlight").count() == 1
            # Formula atom -> drawer (A rides low; B sits under the
            # open drawer, which overlays the plot's top edge).
            first.locator(
                ".lex-curve-math-atom .lex-curve-variable-a").hover(force=True)
            assert first.locator(
                ".lex-curve-variable[data-curve-variable='a']"
                ".lex-curve-variable-active").count() == 1
            assert not errors, errors
        finally:
            browser.close()


def test_each_stage_owns_its_color_and_glow():
    with sync_playwright() as play:
        browser, page, errors = open_page(play)
        try:
            second = page.locator(".lex-curve-editor").nth(1)
            token = second.locator(
                ".lex-curve-math-atom .lex-curve-variable-t1")
            assert token.count() == 1
            assert token.first.text_content() == "T1"
            colors = page.evaluate(
                "() => [...document.querySelectorAll("
                "'.lex-curve-editor')[1].querySelectorAll("
                "'.lex-curve-variable-name')].map(node => "
                "getComputedStyle(node).color)")
            assert len(set(colors)) == 3, colors
            # T1 lights its own token and drawer entry only: T2 and V1
            # stay dark.
            second.hover()
            second.locator(
                ".lex-curve-variable[data-curve-variable='t1']").hover()
            assert second.locator(
                ".lex-curve-math-atom .lex-curve-variable-t1"
                ".lex-curve-variable-highlight").count() == 1
            assert second.locator(
                ".lex-curve-variable[data-curve-variable='t1']"
                ".lex-curve-variable-active").count() == 1
            assert second.locator(
                ".lex-curve-variable[data-curve-variable='t2']"
                ".lex-curve-variable-active").count() == 0
            # The reverse direction: a V1 atom lights the V1 drawer entry.
            second.locator(
                ".lex-curve-math-atom .lex-curve-variable-v1").hover(force=True)
            assert second.locator(
                ".lex-curve-variable[data-curve-variable='v1']"
                ".lex-curve-variable-active").count() == 1
            assert not errors, errors
        finally:
            browser.close()


def test_formula_without_variables_stays_uncolored():
    with sync_playwright() as play:
        browser, page, errors = open_page(play)
        try:
            assert page.locator(
                "main > .lex-math-formula [class*='lex-curve-variable-']").count() == 0
            assert not errors, errors
        finally:
            browser.close()
