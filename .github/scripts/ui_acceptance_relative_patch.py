from pathlib import Path

path = Path(__file__).with_name("ui_visual_acceptance.py")
text = path.read_text(encoding="utf-8")
old = '''            icon = page.locator('.lex-detail-panel-icon').first
            icon_box = icon.bounding_box()
            icon.click(); page.wait_for_timeout(100)
            drawer = page.locator('.lex-model-preview-drawer').first
            close = page.locator('.lex-model-preview-close').first
            assert drawer.is_visible(), (width, 'shared model preview did not open')
            assert close.is_visible(), (width, 'model preview X is not visible')
            open_icon_box = icon.bounding_box()
            assert max(abs(icon_box[k] - open_icon_box[k]) for k in ('x','y','width','height')) <= 0.5, (width, 'model preview changed the header-icon control slot', icon_box, open_icon_box)
            assert icon.get_attribute('aria-label') == 'Close model preview', (width, 'header icon did not become the close control')
            icon.click(); page.wait_for_timeout(80)
            assert not drawer.is_visible(), (width, 'shared model preview did not close')
'''
new = '''            icon = page.locator('.lex-detail-panel-icon').first
            heading = page.locator('.lex-detail-panel-heading').first
            icon_box = icon.bounding_box(); heading_box = heading.bounding_box()
            icon.click(); page.wait_for_timeout(100)
            drawer = page.locator('.lex-model-preview-drawer').first
            close = page.locator('.lex-model-preview-close').first
            assert drawer.is_visible(), (width, 'shared model preview did not open')
            assert close.is_visible(), (width, 'model preview X is not visible')
            open_icon_box = icon.bounding_box(); open_heading_box = heading.bounding_box()
            # The X is a state of the exact same header control. Compare the
            # control slot relative to its Detail header rather than raw viewport
            # coordinates: Playwright may scroll an ancestor a couple pixels as
            # part of locator.click(), which moves the whole header and is not a
            # movement of the X within the header.
            before_rel = {k: icon_box[k] - heading_box[k] for k in ('x','y')}
            after_rel = {k: open_icon_box[k] - open_heading_box[k] for k in ('x','y')}
            assert abs(icon_box['width'] - open_icon_box['width']) <= .5 and abs(icon_box['height'] - open_icon_box['height']) <= .5, (width, 'model preview changed header-control size', icon_box, open_icon_box)
            assert max(abs(before_rel[k] - after_rel[k]) for k in ('x','y')) <= .5, (width, 'model preview X moved within the header slot', icon_box, open_icon_box, heading_box, open_heading_box, before_rel, after_rel)
            assert abs(heading_box['height'] - open_heading_box['height']) <= .5, (width, 'model preview reflowed Detail header height', heading_box, open_heading_box)
            assert icon.get_attribute('aria-label') == 'Close model preview', (width, 'header icon did not become the close control')
            icon.click(); page.wait_for_timeout(80)
            assert not drawer.is_visible(), (width, 'shared model preview did not close')
'''
if old not in text:
    raise SystemExit('preview acceptance block not found')
path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
