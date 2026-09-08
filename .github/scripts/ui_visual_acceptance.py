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


def center(rect: dict) -> tuple[float, float]:
    return rect["x"] + rect["width"] / 2, rect["y"] + rect["height"] / 2


def hover_barrel_control(page, button):
    divider = button.locator("xpath=ancestor::*[contains(concat(' ',normalize-space(@class),' '),' lex-panel-layout-divider ')][1]")
    assert divider.count(), "barrel control is not attached to a shared divider"
    divider.hover()
    page.wait_for_timeout(70)


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

            # 1-panel: label geometry, info-bubble placement, Boolean ref rail,
            # and whole-property Boolean activation are all shared behavior.
            page.evaluate("navigate('one')")
            first_field = page.locator('.lex-detail-field').first
            first_geom = first_field.evaluate("""e=>{
              const field=e.getBoundingClientRect();
              const label=e.querySelector('.lex-detail-field-label');
              const help=e.querySelector('.lex-info-help');
              const lb=label.getBoundingClientRect(), hb=help?.getBoundingClientRect();
              const glyph=help?.querySelector(':scope > span');
              const gb=glyph?.getBoundingClientRect();
              const hs=help?getComputedStyle(help):null, gs=glyph?getComputedStyle(glyph):null;
              const range=document.createRange();
              const text=[...label.childNodes].find(n=>n.nodeType===Node.TEXT_NODE&&n.textContent.trim());
              if(text) range.selectNodeContents(text);
              const tb=text?range.getBoundingClientRect():lb;
              return {field:{left:field.left,right:field.right,width:field.width,height:field.height},
                label:{left:lb.left,right:lb.right,width:lb.width,height:lb.height,scrollWidth:label.scrollWidth,clientWidth:label.clientWidth,scrollHeight:label.scrollHeight,clientHeight:label.clientHeight},
                text:{left:tb.left,right:tb.right,width:tb.width},
                help:hb?{left:hb.left,right:hb.right,top:hb.top,bottom:hb.bottom,width:hb.width,height:hb.height,center:hb.left+hb.width/2}:null,
                glyph:gb?{left:gb.left,right:gb.right,top:gb.top,bottom:gb.bottom,width:gb.width,height:gb.height,
                  centerX:gb.left+gb.width/2,centerY:gb.top+gb.height/2,fontFamily:hs.fontFamily,transform:gs.transform}:null};
            }""")
            assert first_geom['label']['scrollWidth'] <= first_geom['label']['clientWidth'] + 1, (width, 'property label overflows horizontally', first_geom)
            assert first_geom['label']['scrollHeight'] <= first_geom['label']['clientHeight'] + 1, (width, 'property label changes row height/overflows vertically', first_geom)
            if first_geom['help']:
                desired = (first_geom['field']['left'] + first_geom['text']['right']) / 2
                assert abs(first_geom['help']['center'] - desired) <= 6, (width, 'info bubble is not centred between panel edge and property text', desired, first_geom)
                assert abs(first_geom['help']['width'] - first_geom['help']['height']) <= 0.5, (width, 'info bubble is not circular', first_geom)
                glyph = first_geom['glyph']
                assert glyph, (width, 'info bubble ? glyph is missing', first_geom)
                bubble_cx = first_geom['help']['left'] + first_geom['help']['width'] / 2
                bubble_cy = first_geom['help']['top'] + first_geom['help']['height'] / 2
                assert abs(glyph['centerX'] - bubble_cx) <= 0.75, (width, 'info bubble ? is not horizontally centered', first_geom)
                assert abs(glyph['centerY'] - bubble_cy) <= 1.0, (width, 'info bubble ? is not vertically centered', first_geom)
                assert 'Segoe UI Symbol' in glyph['fontFamily'], (width, 'info bubble inherited game typography', glyph)
                assert glyph['transform'] != 'none', (width, 'info bubble lost its optical punctuation adjustment', glyph)

            enabled = page.locator('.lex-boolean-field').first
            bool_ref = enabled.evaluate("""e=>{
              const ref=e.querySelector('.lex-reference-values .lex-reference-value');
              const tag=ref?.querySelector('.lex-reference-tag');
              const mark=ref?.querySelector('.lex-boolean-mark');
              const next=e.nextElementSibling;
              if(!ref||!tag||!mark||!next)return null;
              const rb=ref.getBoundingClientRect(),tb=tag.getBoundingClientRect(),mb=mark.getBoundingClientRect(),nb=next.getBoundingClientRect();
              return {gap:mb.left-tb.right, tagY:tb.top+tb.height/2, markY:mb.top+mb.height/2,
                bottomGap:nb.top-rb.bottom, ref:{left:rb.left,right:rb.right,top:rb.top,bottom:rb.bottom}};
            }""")
            assert bool_ref, (width, 'Boolean Vanilla reference is missing')
            assert 0 <= bool_ref['gap'] <= 8, (width, 'V is too far from Boolean check/X', bool_ref)
            assert abs(bool_ref['tagY'] - bool_ref['markY']) <= 2, (width, 'Boolean V and check/X are vertically off-centre', bool_ref)
            assert bool_ref['bottomGap'] >= 4, (width, 'Boolean reference has no bottom breathing room', bool_ref)

            checkbox = enabled.locator('input[type=checkbox]').first
            before = checkbox.is_checked()
            enabled.click(position={"x": max(2, enabled.bounding_box()["width"] * .35), "y": enabled.bounding_box()["height"] / 2})
            after = checkbox.is_checked()
            assert before != after, (width, "boolean row did not toggle")
            page.screenshot(path=str(OUT / f"{prefix}-1-panel.png"))

            # Generic model preview: opening the header icon and closing it uses
            # one shared drawer and exactly the same header slot.
            preview = page.evaluate("""()=>{
              const panel=LexeditorUI.detailPanel({
                className:'blank-detail', title:'Preview Contract',
                icon:LexeditorUI.el('span',{},'MODEL'), identity:'TEST', meta:'Shared preview fixture',
                modelPreview:{content:LexeditorUI.el('div',{class:'preview-fixture'},'MODEL PREVIEW')}, body:[]
              });
              document.querySelector('#main').replaceChildren(panel);
              return true;
            }""")
            assert preview
            icon = page.locator('.lex-detail-panel-icon').first
            heading = page.locator('.lex-detail-panel-heading').first
            icon.hover(); page.wait_for_timeout(50)
            icon_box = icon.bounding_box(); heading_box = heading.bounding_box()
            icon.click(); page.wait_for_timeout(100)
            drawer = page.locator('.lex-model-preview-drawer').first
            close = page.locator('.lex-model-preview-close').first
            assert drawer.is_visible(), (width, 'shared model preview did not open')
            assert close.is_visible(), (width, 'model preview X is not visible')
            open_icon_box = icon.bounding_box(); open_heading_box = heading.bounding_box()
            # Compare the clicked/hovered header-control slot with its open X
            # state. Playwright, like a real pointer, moves onto the control
            # before the click; measuring the idle state instead tests a hover
            # transition rather than whether the X replaces the clicked icon.
            before_rel = {k: icon_box[k] - heading_box[k] for k in ('x','y')}
            after_rel = {k: open_icon_box[k] - open_heading_box[k] for k in ('x','y')}
            assert abs(icon_box['width'] - open_icon_box['width']) <= .5 and abs(icon_box['height'] - open_icon_box['height']) <= .5, (width, 'model preview changed header-control size', icon_box, open_icon_box)
            assert max(abs(before_rel[k] - after_rel[k]) for k in ('x','y')) <= .5, (width, 'model preview X moved within the clicked header slot', icon_box, open_icon_box, heading_box, open_heading_box, before_rel, after_rel)
            assert abs(heading_box['height'] - open_heading_box['height']) <= .5, (width, 'model preview reflowed Detail header height', heading_box, open_heading_box)
            assert icon.get_attribute('aria-label') == 'Close model preview', (width, 'header icon did not become the close control')
            icon.click(); page.wait_for_timeout(80)
            assert not drawer.is_visible(), (width, 'shared model preview did not close')

            # Standard 2-panel table. Pinning Enabled must work without moving
            # the split; sorting Value must preserve its property label/help.
            page.evaluate("navigate('two')")
            page.wait_for_selector('.lex-paged-list-detail')
            page.wait_for_timeout(200)
            detail_before = page.locator('.lex-detail-panel').last.bounding_box()
            enabled_pin = page.locator('[data-lex-pin-column="enabled"]').first
            if enabled_pin.count():
                was_pressed = enabled_pin.get_attribute('aria-pressed')
                enabled_pin.click(); page.wait_for_timeout(180)
                enabled_pin = page.locator('[data-lex-pin-column="enabled"]').first
                assert enabled_pin.get_attribute('aria-pressed') != was_pressed, (width, "Enabled pin did not toggle")
                detail_after = page.locator('.lex-detail-panel').last.bounding_box()
                assert abs(detail_after['x'] - detail_before['x']) < 3, (width, 'pinning flashed/reset the split', detail_before, detail_after)

            value_header = page.locator('.lex-column-list-head-cell[data-column-key="value"]').first
            if value_header.count():
                value_header.click(); page.wait_for_timeout(120)
                sorted_field = page.locator('.lex-detail-field[data-lex-property="value"][data-lex-sort]').first
                assert sorted_field.count(), (width, 'Value property did not receive sort state')
                assert sorted_field.locator('.lex-detail-field-label').is_visible(), (width, 'sorted property label disappeared')
                help_node = sorted_field.locator('.lex-info-help').first
                assert help_node.count() and help_node.is_visible(), (width, 'sorted property info bubble disappeared')

            # Editable cells enter edit mode without changing row/column geometry.
            cell = page.locator('.lex-column-list-cell[data-column-key="name"]').first
            if cell.count():
                cell_before = cell.bounding_box(); row_before = cell.locator('xpath=..').bounding_box()
                cell.dblclick(); page.wait_for_timeout(80)
                cell_after = cell.bounding_box(); row_after = cell.locator('xpath=..').bounding_box()
                assert abs(cell_after['width'] - cell_before['width']) < 1 and abs(row_after['height'] - row_before['height']) < 1, (width, cell_before, cell_after, row_before, row_after)
                editor_style = cell.locator('input,select,textarea').first.evaluate("e=>({font:getComputedStyle(e).font,lineHeight:getComputedStyle(e).lineHeight})")
                assert editor_style['font'], editor_style
                page.keyboard.press('Escape')

            # Property -> column hover is the reverse of column -> property hover.
            prop = page.locator('[data-lex-property="name"]').first
            if prop.count():
                prop.hover(); page.wait_for_timeout(60)
                assert prop.evaluate("e=>e.classList.contains('lex-column-lit')"), (width, "property did not self-highlight")
                counterpart = page.locator('[data-column-key="name"]').first
                assert counterpart.evaluate("e=>e.classList.contains('lex-column-lit')"), (width, "column did not follow property hover")

            # Barrel count must be genuinely clickable through the divider and
            # both increasing and reducing it must preserve usable page height.
            grid = page.locator('.lex-barrelled-master').first
            height_one = grid.bounding_box()['height']
            count_one = page.locator('.lex-column-list[data-lex-barrel]').count()
            inc = page.locator('.lex-barrel-increase').first
            if inc.count() and not inc.is_disabled():
                hover_barrel_control(page, inc); inc.click(); page.wait_for_timeout(250)
                height_two = page.locator('.lex-barrelled-master').first.bounding_box()['height']
                count_two = page.locator('.lex-column-list[data-lex-barrel]').count()
                assert count_two == count_one + 1, (width, 'barrel increase did not add a table', count_one, count_two)
                assert height_two >= height_one * .85, (width, 'barrel increase collapsed the page', height_one, height_two)
                dec = page.locator('.lex-barrel-decrease').first
                hover_barrel_control(page, dec); dec.click(); page.wait_for_timeout(250)
                height_back = page.locator('.lex-barrelled-master').first.bounding_box()['height']
                count_back = page.locator('.lex-column-list[data-lex-barrel]').count()
                assert count_back == count_one, (width, 'barrel decrease did not remove a table', count_one, count_back)
                assert height_back >= height_one * .85, (width, 'reducing barrels collapsed the panels vertically', height_one, height_back)
            else:
                height_two = height_back = height_one
                count_two = count_back = count_one
            page.screenshot(path=str(OUT / f"{prefix}-2-panels.png"))

            # Three-panel view exposes the same working barrel control. A nested
            # two-panel preset must not lose the control when a third pane wraps it.
            page.evaluate("navigate('three')"); page.wait_for_timeout(220)
            three_outer = page.locator('.blank-three-layout').first.bounding_box()
            three_count_before = page.locator('.lex-column-list[data-lex-barrel]').count()
            three_inc = page.locator('.lex-barrel-increase').first
            if three_inc.count() and not three_inc.is_disabled():
                hover_barrel_control(page, three_inc); three_inc.click(); page.wait_for_timeout(250)
                three_count_after = page.locator('.lex-column-list[data-lex-barrel]').count()
                three_outer_after = page.locator('.blank-three-layout').first.bounding_box()
                assert three_count_after == three_count_before + 1, (width, '3-panel barrel control cannot increase', three_count_before, three_count_after)
                assert three_outer_after['height'] >= three_outer['height'] * .85, (width, '3-panel barrel change collapsed outer layout', three_outer, three_outer_after)
                three_dec = page.locator('.lex-barrel-decrease').first
                hover_barrel_control(page, three_dec); three_dec.click(); page.wait_for_timeout(220)
                assert page.locator('.lex-column-list[data-lex-barrel]').count() == three_count_before, (width, '3-panel barrel control cannot decrease')
            page.screenshot(path=str(OUT / f"{prefix}-3-panels.png"))

            # Tweaks: checkbox arrow points into the checkbox instead of hiding
            # underneath it; numeric track/fill stays inside its property box.
            page.evaluate("navigate('tweaks')"); page.wait_for_timeout(150)
            bool_field = page.locator('.lex-boolean-field').first
            arrow = bool_field.locator('.lex-field-boolean-arrow').first
            tweak_checkbox = bool_field.locator('input[type=checkbox]').first
            if arrow.count() and tweak_checkbox.count():
                arrow_box = arrow.bounding_box(); checkbox_box = tweak_checkbox.bounding_box()
                assert arrow_box['x'] + arrow_box['width'] <= checkbox_box['x'] + 3, (width, 'Boolean arrow is underneath/past the checkbox', arrow_box, checkbox_box)
                assert abs(center(arrow_box)[1] - center(checkbox_box)[1]) <= 4, (width, 'Boolean arrow is vertically misaligned', arrow_box, checkbox_box)
            tweak_field = page.locator('.lex-detail-field').nth(1)
            tweak_input = tweak_field.locator('input[type=number]').first
            tweak_box = tweak_field.bounding_box(); input_box = tweak_input.bounding_box()
            assert input_box['x'] >= tweak_box['x'] - 1 and input_box['x'] + input_box['width'] <= tweak_box['x'] + tweak_box['width'] + 1, (width, 'numeric input escaped property box', tweak_box, input_box)
            overflow = tweak_field.evaluate("e=>e.scrollWidth>e.clientWidth+1")
            assert not overflow, (width, 'numeric slider/fill background causes horizontal overflow')
            for selector in ('.lex-value-fill','.lex-value-handle'):
                node = tweak_field.locator(selector).first
                if node.count():
                    nb = node.bounding_box()
                    assert nb['x'] >= tweak_box['x'] - 2 and nb['x'] + nb['width'] <= tweak_box['x'] + tweak_box['width'] + 2, (width, selector, 'escaped property box', tweak_box, nb)
            page.screenshot(path=str(OUT / f"{prefix}-tweaks.png"))

            # Graph contract: large all-caps unsquashed title, no redundant
            # pseudo-title box, variables above the plot, and every right-axis
            # string (name + range endpoints) rotated in the graph margin.
            page.evaluate("navigate('graphs')"); page.wait_for_timeout(180)
            title = page.locator('.lex-curve-heading-title').first
            title_text = title.inner_text()
            title_style = title.evaluate("e=>({fontSize:parseFloat(getComputedStyle(e).fontSize),transform:getComputedStyle(e).transform,fontStretch:getComputedStyle(e).fontStretch})")
            variables_box = page.locator('.lex-curve-variable-strip').first.bounding_box()
            plot_box = page.locator('.lex-curve-plot').first.bounding_box()
            svg_box = page.locator('.lex-curve-svg').first.bounding_box()
            editor = page.locator('.lex-curve-editor').first
            pseudo = editor.evaluate("e=>({content:getComputedStyle(e,'::before').content,display:getComputedStyle(e,'::before').display})")
            y_name = page.locator('.lex-curve-axis-name-y').first
            axis_top = page.locator('.lex-curve-axis-top').first
            axis_bottom = page.locator('.lex-curve-axis-bottom').first
            axis_start = page.locator('.lex-curve-axis-start').first
            axis_end = page.locator('.lex-curve-axis-end').first
            assert title_text == title_text.upper() and title_style['fontSize'] >= 26, (width, title_text, title_style)
            assert title_style['transform'] == 'none', (width, 'graph title is geometrically squashed/stretched', title_style)
            assert pseudo['display'] == 'none' or pseudo['content'] in ('none','""'), (width, 'redundant graph-name pseudo box still exists', pseudo)
            assert variables_box['y'] < plot_box['y'] + 2, (width, 'variable panel is not top-mounted', variables_box, plot_box)
            for node in (y_name, axis_top, axis_bottom):
                assert node.evaluate("e=>getComputedStyle(e).writingMode").startswith('vertical'), (width, 'right-axis text is not vertical', node.get_attribute('class'))
            for node in (axis_top, axis_bottom, y_name):
                nb = node.bounding_box(); assert nb['x'] + nb['width'] >= svg_box['x'] + svg_box['width'] - 2, (width, 'right-axis text is not in right margin', node.get_attribute('class'), nb, svg_box)
            for node in (axis_start, axis_end):
                nb = node.bounding_box(); assert nb['y'] + nb['height'] >= svg_box['y'] + svg_box['height'] - 2, (width, 'x-axis number is not in bottom margin', node.get_attribute('class'), nb, svg_box)
            page.screenshot(path=str(OUT / f"{prefix}-graphs.png"))

            # Shortcut badge has one implementation per tab, never an added hover duplicate.
            tab_buttons = page.locator('nav button[data-tab]')
            duplicate = page.evaluate("[...document.querySelectorAll('nav button[data-tab]')].some(b=>b.querySelectorAll('.lex-tab-shortcut,.lex-tab-ordinal').length>1)")
            assert not duplicate, (width, "duplicate shortcut badge")

            # Common detail-label lane remains ~10% without allowing a long
            # label to increase a simple row's height.
            page.evaluate("navigate('one')")
            field = page.locator('.lex-detail-field').first
            label = field.locator('.lex-detail-field-label').first
            field_box = field.bounding_box(); label_box = label.bounding_box()
            label_ratio = label_box['width'] / field_box['width'] if field_box['width'] else 0
            assert .07 <= label_ratio <= .13, (width, "label lane is not approximately 10%", label_ratio)
            # Test label fitting with two otherwise identical rows. Different
            # control types legitimately reserve different vertical space (for
            # example a provenance/ref rail), so comparing arbitrary gallery
            # rows would not test the user's requirement. A long PROPERTY NAME
            # must fit by wrapping/scaling without making its row taller.
            page.evaluate("""()=>{
              const make = label => LexeditorUI.detailField({
                label,
                control: LexeditorUI.el('input',{type:'text',value:'x'})
              });
              const panel = LexeditorUI.detailPanel({
                className:'blank-detail', title:'Label Fit Contract',
                icon:LexeditorUI.el('span',{},'L'), identity:'TEST', meta:'Shared label fitting',
                body:[LexeditorUI.detailSection({title:'LABELS',body:[
                  make('SHORT'),
                  make('A DELIBERATELY VERY LONG PROPERTY NAME')
                ]})]
              });
              document.querySelector('#main').replaceChildren(panel);
            }""")
            page.wait_for_timeout(120)
            fit_fields = page.locator('.lex-detail-field')
            simple_heights = [fit_fields.nth(i).bounding_box()['height'] for i in range(2)]
            assert abs(simple_heights[0] - simple_heights[1]) <= 2, (width, 'long property name changed row height', simple_heights)
            long_label = fit_fields.nth(1).locator('.lex-detail-field-label')
            long_fit = long_label.evaluate("e=>({sw:e.scrollWidth,cw:e.clientWidth,sh:e.scrollHeight,ch:e.clientHeight,font:getComputedStyle(e).fontSize})")
            assert long_fit['sw'] <= long_fit['cw'] + 1 and long_fit['sh'] <= long_fit['ch'] + 1, (width, 'long property name did not fit its fixed label lane', long_fit)

            # set_content() runs the fixture at about:blank with a fake <base>.
            # The app's final history.replaceState therefore raises one expected
            # null-origin security error that cannot occur in the real HTTP/WebView
            # host. Keep every other page error fatal.
            real_errors = [error for error in errors if not (
                "Failed to execute 'replaceState' on 'History'" in error and
                "origin 'null'" in error
            )]
            results[prefix] = {
                "errors": real_errors,
                "booleanToggled": [before, after],
                "booleanRef": bool_ref,
                "barrelHeights": [round(height_one, 2), round(height_two, 2), round(height_back, 2)],
                "barrelCounts": [count_one, count_two, count_back],
                "labelRatio": round(label_ratio, 4),
                "infoGeometry": first_geom,
                "graphTitle": {"text": title_text, **title_style},
                "tabCount": tab_buttons.count(),
            }
            assert not real_errors, (width, real_errors)
            page.close()
    finally:
        browser.close()

(OUT / "results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
print(json.dumps(results, indent=2))
