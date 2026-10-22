"""Ctrl+Z undoes a value edit even when no field has focus.

Typing commits on Enter and slider drags commit on release, but both leave
focus on the page body: there is no caret anywhere. The key handler used to
swallow Ctrl+Z unless a field had focus, so undo silently did nothing after
exactly the edits that leave focus behind. Only real free text keeps native
undo now, and dialogs block the shortcut.
"""
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive, make_menu_archive, make_text_archive  # noqa: E402
from plugins.ds1 import texts  # noqa: E402
from plugins.ds1.plugin import DS1Session  # noqa: E402
from plugins.ds1.store import MARKER, RELATIVE  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

NUMBER = "#main .lex-detail-field input[type=number]"


@contextmanager
def running_app():
    """Boot the real DS1 UI over fixture archives, yield (page, errors)."""
    with tempfile.TemporaryDirectory(prefix="lexeditor-ds1-value-undo-") as folder:
        temp = Path(folder)
        game, mod = temp / "game", temp / "mod"
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        (game / texts.RELATIVE).parent.mkdir(parents=True)
        (game / texts.RELATIVE).write_bytes(make_text_archive())
        (game / texts.MENU_RELATIVE).write_bytes(make_menu_archive())
        mod.mkdir()
        (mod / MARKER).touch()
        session = DS1Session({"LEXEDITOR_DS1_ROOT": str(game),
                              "LEXEDITOR_DS1_PROJECT": str(mod),
                              "LEXEDITOR_NO_MOD": "0",
                              "LEXEDITOR_MOD_READ_ONLY": "0"})
        session.start()
        try:
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={"width": 1700, "height": 900})
                    page.set_default_timeout(60000)
                    errors = []
                    page.on("pageerror", lambda event: errors.append(str(event)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=120000)
                    page.wait_for_function("state.tab==='items'&&state.rows&&state.rows.length")
                    page.wait_for_timeout(2500)
                    yield page, errors
                finally:
                    browser.close()
        finally:
            session.stop()


def first_number_input(page):
    """Click through the Items subtabs until a number field is showing."""
    page.evaluate("""() => {
      const tabs = [...document.querySelectorAll(
        '#main .lex-subtab-button[data-subtab]')];
      for (const tab of tabs) {
        tab.click();
        if (document.querySelector('#main .lex-detail-field input[type=number]')) break;
      }
    }""")
    page.wait_for_timeout(800)
    target = page.locator(NUMBER).first
    assert target.count() == 1, "no number field found in any Items subtab"
    return target


def number_value(page):
    return page.evaluate(f"document.querySelector('{NUMBER}').value")


def blur_to_body(page):
    """Leave focus where a click on empty space leaves it: the body."""
    page.evaluate("document.activeElement?.blur()")
    assert page.evaluate("document.activeElement === document.body")


def test_typed_edit_undoes_from_body_focus():
    with running_app() as (page, errors):
        target = first_number_input(page)
        before = target.input_value()
        typed = "7" if before != "7" else "9"
        target.fill(typed)
        target.press("Enter")
        page.wait_for_timeout(1200)
        assert number_value(page) == typed, "the typed edit never committed"
        blur_to_body(page)
        page.keyboard.press("Control+z")
        page.wait_for_timeout(1200)
        assert number_value(page) == before, "Ctrl+Z from body focus did not undo"
        assert errors == [], errors[:3]


def test_slider_drag_commits_and_undoes():
    with running_app() as (page, errors):
        target = first_number_input(page)
        key = target.get_attribute("data-field-key")
        field = page.locator(f"#main .lex-detail-field:has(input[data-field-key='{key}'])")
        target.fill("5")
        target.press("Enter")
        page.wait_for_timeout(1200)
        assert number_value(page) == "5", "the typed edit never committed"
        handle = field.locator(".lex-value-handle")
        assert handle.count() == 1, "this field has no slider of its own"
        field.hover(force=True)
        page.wait_for_timeout(400)
        revealed = page.evaluate(
            f"""() => getComputedStyle(document.querySelector(
              "#main .lex-detail-field:has(input[data-field-key='{key}'])"
              + " .lex-value-handle")).opacity""")
        assert revealed != "0", "the slider handle never revealed on hover"
        box = handle.bounding_box()
        start_x = box["x"] + box["width"] / 2
        start_y = box["y"] + box["height"] / 2
        under = page.evaluate(
            f"document.elementFromPoint({start_x}, {start_y})?.className")
        assert "lex-value-handle" in under, f"the cursor misses the handle: {under}"
        end = target.bounding_box()
        page.mouse.move(start_x, start_y)
        page.mouse.down()
        page.mouse.move(end["x"] + end["width"] * 0.9, start_y, steps=12)
        page.mouse.up()
        page.wait_for_timeout(1200)
        assert number_value(page) != "5", "the slider drag never committed"
        blur_to_body(page)
        page.keyboard.press("Control+z")
        page.wait_for_timeout(1200)
        assert number_value(page) == "5", "Ctrl+Z did not undo the drag"
        assert errors == [], errors[:3]
