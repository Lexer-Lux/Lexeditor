from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "out" / "ui-visual-acceptance"
OUT.mkdir(parents=True, exist_ok=True)


def blank_html() -> str:
    html = (ROOT / "games" / "blank" / "editor.html").read_text(encoding="utf-8")
    html = html.replace("<head>", '<head><base href="http://127.0.0.1:9/">', 1)
    html = html.replace(
        '<link rel="stylesheet" href="/shared/framework.css">',
        "<style>" + (ROOT / "ui" / "framework.css").read_text(encoding="utf-8") + "</style>",
    )
    settings = {
        "developerMode": True,
        "developerAuthorized": True,
        "developerLogin": "Lexer-Lux",
        "updateCheckFrequency": "daily",
        "updateCheckChoices": [
            {"value": "daily", "label": "Daily"},
            {"value": "weekly", "label": "Weekly"},
        ],
        "hoverableAltClick": False,
        "selectionHoldMs": 650,
        "tableRowsPerPage": 12,
        "panelGapPercent": 1,
        "residentHandleWidthPercent": 5,
        "mainMenuHeightPercent": 9,
        "soundEnabled": False,
        "soundVolumePercent": 0,
        "absentGameDesaturationPercent": 75,
        "globalMessageRarity": 3,
        "loadingTransitionMinimumSeconds": 0,
        "viewPreferences": {},
        "defaultValues": {
            "updateCheckFrequency": "daily",
            "hoverableAltClick": False,
            "selectionHoldMs": 650,
            "tableRowsPerPage": 12,
            "panelGapPercent": 1,
            "residentHandleWidthPercent": 5,
            "mainMenuHeightPercent": 9,
            "soundEnabled": False,
            "soundVolumePercent": 0,
            "absentGameDesaturationPercent": 75,
            "globalMessageRarity": 3,
            "loadingTransitionMinimumSeconds": 0,
        },
    }
    stub = f"""
    window.__fixtureSettings={json.dumps(settings)};
    window.pywebview={{api:new Proxy({{}},{{get:(_t,name)=>(...args)=>Promise.resolve((()=>{{
      if(name==='lexeditor_settings'||name==='save_lexeditor_settings'||name==='save_developer_setting_defaults'||name==='save_lexeditor_view_preference'||name==='clear_lexeditor_view_preference')return structuredClone(window.__fixtureSettings);
      if(name==='default_views')return {{views:{{}}}};
      if(name==='github_repository')return {{repository:'Lexer-Lux/Lexeditor',login:'Lexer-Lux'}};
      if(name==='github_issues')return {{issues:[],state:'all'}};
      if(name==='github_labels')return {{labels:[]}};
      if(name==='game_process_status')return {{running:false}};
      if(name==='window_state'||name==='window_toggle_maximize')return {{maximized:false,frameless:true}};
      if(name==='transition_snapshot')return {{html:''}};
      if(name==='editor_ready'||name==='set_dirty_count')return true;
      return {{}};
    }})())}})}};
    """
    html = html.replace(
        '<script src="/shared/framework.js"></script>',
        "<script>" + stub + "</script><script>" + (ROOT / "ui" / "framework.js").read_text(encoding="utf-8") + "</script>",
    )
    return html


def box(page, selector: str):
    b = page.locator(selector).first.bounding_box()
    return {k: round(v, 2) for k, v in b.items()} if b else None


results = {}
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=shutil.which("chromium") or None, headless=True, args=["--no-sandbox"])
    try:
        for width, height in ((1600, 900), (1000, 700)):
            page = browser.new_page(viewport={"width": width, "height": height})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.set_content(blank_html(), wait_until="domcontentloaded")
            page.wait_for_function("typeof shell==='object' && !!document.querySelector('.lex-detail-panel')")
            page.wait_for_timeout(250)

            prefix = f"blank-{width}"
            page.screenshot(path=str(OUT / f"{prefix}-1-panel.png"))

            # A lone Boolean property is toggled by its whole row, not only the tiny checkbox.
            page.evaluate("navigate('one')")
            enabled = page.locator('.lex-boolean-field').first
            checkbox = enabled.locator('input[type=checkbox]').first
            before = checkbox.is_checked()
            enabled.click(position={"x": max(2, enabled.bounding_box()["width"] * .35), "y": enabled.bounding_box()["height"] / 2})
            after = checkbox.is_checked()
            assert before != after, (width, "boolean row did not toggle")

            # Standard 2-panel table. Pinning Enabled must work without moving the detail split.
            page.evaluate("navigate('two')")
            page.wait_for_selector('.lex-paged-list-detail')
            page.wait_for_timeout(200)
            root = page.locator('.lex-paged-list-detail').first
            before_root = root.bounding_box()
            detail_before = page.locator('.lex-detail-panel').last.bounding_box()
            enabled_pin = page.locator('[data-lex-pin-column="enabled"]').first
            if enabled_pin.count():
                was_pressed = enabled_pin.get_attribute('aria-pressed')
                enabled_pin.click()
                page.wait_for_timeout(180)
                enabled_pin = page.locator('[data-lex-pin-column="enabled"]').first
                assert enabled_pin.get_attribute('aria-pressed') != was_pressed, (width, "Enabled pin did not toggle")
                detail_after = page.locator('.lex-detail-panel').last.bounding_box()
                assert abs(detail_after['x'] - detail_before['x']) < 3, (width, detail_before, detail_after)

            # Editable cells enter edit mode without changing row/column geometry.
            cell = page.locator('.lex-column-list-cell[data-column-key="name"]').first
            if cell.count():
                cell_before = cell.bounding_box()
                row_before = cell.locator('xpath=..').bounding_box()
                cell.dblclick()
                page.wait_for_timeout(80)
                cell_after = cell.bounding_box()
                row_after = cell.locator('xpath=..').bounding_box()
                assert abs(cell_after['width'] - cell_before['width']) < 1 and abs(row_after['height'] - row_before['height']) < 1, (width, cell_before, cell_after, row_before, row_after)
                page.keyboard.press('Escape')

            # Property -> column hover is the reverse of column -> property hover.
            prop = page.locator('[data-lex-property="name"]').first
            if prop.count():
                prop.hover()
                page.wait_for_timeout(60)
                assert prop.evaluate("e=>e.classList.contains('lex-column-lit')"), (width, "property did not self-highlight")
                counterpart = page.locator('[data-column-key="name"]').first
                assert counterpart.evaluate("e=>e.classList.contains('lex-column-lit')"), (width, "column did not follow property hover")

            # Barrel count changes must not collapse the page vertically.
            grid = page.locator('.lex-barrelled-master').first
            height_one = grid.bounding_box()['height']
            inc = page.locator('.lex-barrel-increase').first
            if inc.count() and not inc.is_disabled():
                inc.click()
                page.wait_for_timeout(250)
                height_two = page.locator('.lex-barrelled-master').first.bounding_box()['height']
                assert height_two >= height_one * .85, (width, height_one, height_two)
            else:
                height_two = height_one
            page.screenshot(path=str(OUT / f"{prefix}-2-panels.png"))

            # Three-panel view must expose the barrel control too when records span pages.
            page.evaluate("navigate('three')")
            page.wait_for_timeout(200)
            page.screenshot(path=str(OUT / f"{prefix}-3-panels.png"))

            # Tweaks: checkbox arrow and numeric slider/fill stay inside their property boxes.
            page.evaluate("navigate('tweaks')")
            page.wait_for_timeout(150)
            tweak_field = page.locator('.lex-detail-field').nth(1)
            tweak_input = tweak_field.locator('input[type=number]').first
            tweak_box = tweak_field.bounding_box(); input_box = tweak_input.bounding_box()
            assert input_box['left'] >= tweak_box['left'] - 1 and input_box['right'] <= tweak_box['right'] + 1, (width, tweak_box, input_box)
            page.screenshot(path=str(OUT / f"{prefix}-tweaks.png"))

            # Graph contract: title is upper-case/large, variables precede plot, right-axis text is vertical.
            page.evaluate("navigate('graphs')")
            page.wait_for_timeout(180)
            title = page.locator('.lex-curve-heading-title').first
            title_text = title.inner_text()
            title_size = float(title.evaluate("e=>parseFloat(getComputedStyle(e).fontSize)"))
            variables = page.locator('.lex-curve-variable-strip').first.bounding_box()
            plot = page.locator('.lex-curve-plot').first.bounding_box()
            y_name = page.locator('.lex-curve-axis-name-y').first
            axis_top = page.locator('.lex-curve-axis-top').first
            assert title_text == title_text.upper() and title_size >= 26, (width, title_text, title_size)
            assert variables['y'] < plot['y'], (width, variables, plot)
            assert y_name.evaluate("e=>getComputedStyle(e).writingMode").startswith('vertical'), width
            assert axis_top.evaluate("e=>getComputedStyle(e).writingMode").startswith('vertical'), width
            page.screenshot(path=str(OUT / f"{prefix}-graphs.png"))

            # Shortcut badge has one implementation per tab, never an added hover duplicate.
            tab_buttons = page.locator('nav button[data-tab]')
            duplicate = page.evaluate("[...document.querySelectorAll('nav button[data-tab]')].some(b=>b.querySelectorAll('.lex-tab-shortcut,.lex-tab-ordinal').length>1)")
            assert not duplicate, (width, "duplicate shortcut badge")

            # Common detail-label lane and info bubble geometry.
            page.evaluate("navigate('one')")
            field = page.locator('.lex-detail-field').first
            label = field.locator('.lex-detail-field-label').first
            field_box = field.bounding_box(); label_box = label.bounding_box()
            label_ratio = label_box['width'] / field_box['width'] if field_box['width'] else 0
            assert label_ratio <= .16, (width, "label lane too wide", label_ratio)
            info = field.locator('.lex-info-help').first
            info_box = info.bounding_box() if info.count() else None

            results[prefix] = {
                "errors": errors,
                "booleanToggled": [before, after],
                "barrelHeights": [round(height_one, 2), round(height_two, 2)],
                "labelRatio": round(label_ratio, 4),
                "infoBubble": info_box,
                "graphTitle": {"text": title_text, "fontSize": title_size},
                "tabCount": tab_buttons.count(),
            }
            assert not errors, (width, errors)
            page.close()
    finally:
        browser.close()

(OUT / "results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
print(json.dumps(results, indent=2))
