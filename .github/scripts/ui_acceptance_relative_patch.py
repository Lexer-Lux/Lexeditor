from pathlib import Path

path = Path(__file__).with_name("ui_visual_acceptance.py")
text = path.read_text(encoding="utf-8")

# First convert the old viewport-space assertion if it is still present.
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
relative = '''            icon = page.locator('.lex-detail-panel-icon').first
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
'''
if old in text:
    text = text.replace(old, relative, 1)
else:
    # Upgrade the first relative version to measure the actual pre-click hover
    # state. This is idempotent after the replacement.
    old_relative = '''            icon = page.locator('.lex-detail-panel-icon').first
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
    if old_relative in text:
        text = text.replace(old_relative, relative, 1)
    elif relative not in text:
        raise SystemExit('preview acceptance block not found')

path.write_text(text, encoding="utf-8", newline="\n")
