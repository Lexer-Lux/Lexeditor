"""The Palettes page shows the palette itself, not one colour at a time.

Lexer's complaint about this plugin was that its controls "refer to images I
can't see". The palette pages listed 256 colours one row at a time with nothing
to show where a colour sits, so the page now draws the whole palette above the
list and lets a cell choose the colour to edit.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from plugins.chrono_trigger.plugin import ChronoTriggerSession  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402


def main() -> int:
    project = tempfile.TemporaryDirectory(prefix="lexeditor-ct-palette-",
                                          ignore_cleanup_errors=True)
    try:
        with ChronoTriggerSession({"LEXEDITOR_CHRONO_TRIGGER_PROJECT": project.name}) as session:
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1500, "height": 950})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(session.url)
                page.wait_for_function("()=>typeof state!=='undefined'&&!state.busy", timeout=180000)
                page.evaluate("()=>navigate('palettes')")
                page.wait_for_selector(".ct-palette-strip", timeout=60000)
                page.wait_for_function(
                    "()=>document.querySelectorAll('.ct-palette-strip button').length>0",
                    timeout=60000)
                cells = page.locator(".ct-palette-strip button").count()
                assert cells == 256, cells
                first = page.locator(".ct-palette-strip button").first
                assert first.get_attribute("aria-pressed") == "true", "the shown colour is marked"
                # A cell carries the colour it draws, so the picture and the
                # list describe the same thing.
                labelled = first.get_attribute("aria-label")
                assert labelled.startswith("Colour 0 "), labelled
                assert page.evaluate("()=>state.palette.rows[0].hex").lower() in labelled.lower()
                # Choosing a cell chooses that colour in the list.
                page.locator(".ct-palette-strip button").nth(9).click()
                page.wait_for_timeout(400)
                assert page.evaluate("()=>state.selected.palettes") == "9"
                pressed = page.locator('.ct-palette-strip button[aria-pressed="true"]')
                assert pressed.count() == 1 and "Colour 9 " in pressed.get_attribute("aria-label")
                assert not errors, errors
                print(json.dumps({"cells": cells, "palette": page.evaluate(
                    "()=>state.palette.path"), "chosen": 9}, ensure_ascii=True))
                browser.close()
        return 0
    finally:
        project.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
