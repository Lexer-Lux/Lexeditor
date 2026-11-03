"""A section heading drag moves only that section, where the marker shows.

Lexer: dragging Navigation into the first column showed the marker there,
then rearranged every header and left Navigation last. The pager dealt
cards into the shortest lane, so the visual order diverged from the card
list the drop computed in. Lanes now keep reading order: the flattened
lanes always equal the card list, before and after a drop.
"""
from test_shared_ui_feedback import framework, page  # noqa: F401
from test_tab_rename import mount_shell


def mount_sections(page, paginate):
    framework(page)
    mount_shell(page, True)
    page.set_viewport_size({'width': 800, 'height': 700})
    page.add_style_tag(content='.lex-tweak-card-grid{--lex-tweak-card-width:220px}')
    page.evaluate('''(paginate) => {
      const U = LexeditorUI;
      const field = label => U.detailField({label, property: label.toLowerCase(),
        control: U.el('input', {value: label})});
      document.querySelector('main').replaceChildren(U.detailPanel({title: 'Record', paginate,
        body: [
          U.detailSection({title: 'COMBAT', body: [field('Weight')]}),
          U.detailSection({title: 'PROPERTIES', body: [field('Short'), field('Medium'), field('Long'),
            field('End'), field('Wall'), field('Visual'), field('Audio'), field('Smell')]}),
          U.detailSection({title: 'NAVIGATION', body: [field('Cliff'), field('Door')]}),
          U.detailSection({title: 'SENSES', body: [field('Eye'), field('Ear')]}),
        ]}));
    }''', paginate)
    page.wait_for_timeout(200)


def mount_many_sections(page):
    framework(page)
    mount_shell(page, True)
    page.set_viewport_size({'width': 900, 'height': 550})
    page.add_style_tag(content='.lex-tweak-card-grid{--lex-tweak-card-width:220px}')
    page.evaluate('''() => {
      const U = LexeditorUI;
      const field = label => U.detailField({label, property: label.toLowerCase(),
        control: U.el('input', {value: label})});
      const section = title => U.detailSection({title,
        body: ['One', 'Two', 'Three', 'Four', 'Five', 'Six'].map(n => field(title + n))});
      document.querySelector('main').replaceChildren(U.detailPanel({title: 'Record',
        paginate: {inline: true},
        body: ['COMBAT', 'PROPERTIES', 'NAVIGATION', 'SENSES', 'SEARCH', 'RETURN']
          .map(section)}));
    }''')
    page.wait_for_timeout(300)


def card_order(page):
    return page.evaluate('''() => document.querySelector('.lex-tweaks-paged')
      .lexCards().map(card => card.querySelector('.lex-detail-section-title').textContent.trim())''')


def lanes(page):
    return page.evaluate('''() => [...document.querySelectorAll('.lex-tweak-column')]
      .map(col => [...col.querySelectorAll(':scope > .lex-detail-section > .lex-detail-section-title')]
        .map(n => n.textContent.trim()))''')


def reading_order(page):
    return [title for lane in lanes(page) for title in lane]


def drag_last_to_first(page, last_section, first_section='COMBAT'):
    head = page.locator(f'[data-lex-layout-section="{last_section}"] h3')
    target = page.locator(f'[data-lex-layout-section="{first_section}"] h3')
    head.hover()
    head.drag_to(target, target_position={'x': 10, 'y': 2})
    page.wait_for_timeout(200)


def test_unpaged_drop_keeps_reading_order(page, tmp_path):
    mount_sections(page, {'unpaged': True})
    assert card_order(page) == ['COMBAT', 'PROPERTIES', 'NAVIGATION', 'SENSES']
    assert reading_order(page) == card_order(page)
    drag_last_to_first(page, 'NAVIGATION')
    page.screenshot(path=str(tmp_path / 'section-drag.png'))
    assert card_order(page) == ['NAVIGATION', 'COMBAT', 'PROPERTIES', 'SENSES']
    assert reading_order(page) == card_order(page)


def test_unpaged_drop_with_custom_section_present(page, tmp_path):
    mount_sections(page, {'unpaged': True})
    # Hold right on Combat's heading: adds an empty custom section below it.
    combat = page.locator('[data-lex-layout-section="COMBAT"] h3')
    box = combat.bounding_box()
    page.mouse.move(box['x'] + 30, box['y'] + 8)
    page.mouse.down(button='right')
    page.wait_for_timeout(900)
    page.mouse.up(button='right')
    page.wait_for_timeout(200)
    assert page.locator('[data-lex-custom-section="true"]').count() == 1
    assert reading_order(page) == card_order(page)
    drag_last_to_first(page, 'NAVIGATION')
    page.screenshot(path=str(tmp_path / 'section-drag-custom.png'))
    got = card_order(page)
    assert got[0] == 'NAVIGATION', got
    assert sorted(got) == ['COMBAT', 'NAVIGATION', 'New section', 'PROPERTIES', 'SENSES'], got
    assert reading_order(page) == got


def test_paged_drop_stays_on_page_in_order(page, tmp_path):
    mount_many_sections(page)
    starts = page.evaluate("document.querySelector('.lex-tweaks-paged').lexPaging().starts")
    assert len(starts) > 1, starts
    assert reading_order(page) == card_order(page)[:len(reading_order(page))]
    seen = reading_order(page)
    drag_last_to_first(page, seen[-1])
    page.screenshot(path=str(tmp_path / 'section-drag-paged.png'))
    got = card_order(page)
    assert got[0] == seen[-1], got
    assert reading_order(page) == got[:len(reading_order(page))]


def test_unpaged_drop_into_empty_lane_below_its_top_strip(page):
    # Lexer: AI tab, three columns, dev mode - the right lanes would not
    # take a dragged header. An empty lane was only a 96px strip at the
    # grid top; aiming anywhere else in the lane hit the grid, and the
    # drop computation only looked at the column box. The lane now
    # stretches to the grid foot, and aims past it resolve by span.
    mount_sections(page, {'unpaged': True})
    page.evaluate('''() => {
      document.querySelector('main').dataset.lexDetailColumns = '3';
      document.querySelector('.lex-tweaks-paged').lexFitPage();
    }''')
    page.wait_for_timeout(200)
    # Vacate a lane: SENSES and NAVIGATION join COMBAT's lane, so one of
    # the three lanes must empty whatever the opening deal was.
    for name in ('SENSES', 'NAVIGATION'):
        head = page.locator(f'[data-lex-layout-section="{name}"] h3')
        first = page.locator('[data-lex-layout-section="COMBAT"]')
        box = first.bounding_box()
        head.drag_to(first, target_position={'x': 10, 'y': box['height'] - 4})
        page.wait_for_timeout(200)
    deal = lanes(page)
    empty = next((i for i, lane in enumerate(deal) if not lane), -1)
    assert empty >= 0, deal
    lane = page.locator('.lex-tweak-column').nth(empty)
    box = lane.bounding_box()
    # Past the old 96px strip: pre-fix this aim hit the grid and refused.
    assert box['height'] > 160, box
    point = [box['x'] + box['width'] / 2, box['y'] + 160]
    hit = page.evaluate('([x, y]) => document.elementFromPoint(x, y)?.className', point)
    assert hit == 'lex-tweak-column', hit
    page.locator('[data-lex-layout-section="PROPERTIES"] h3').drag_to(
        lane, target_position={'x': box['width'] / 2, 'y': 160})
    page.wait_for_timeout(200)
    got = card_order(page)
    assert lanes(page)[empty] == ['PROPERTIES'], lanes(page)
    assert reading_order(page) == got


def test_unpaged_header_drop_into_lane_gap_beside_empty_lane(page):
    # The gap between lanes is grid, not a column box: aiming into the
    # gap beside an empty lane still drops into that lane, by span.
    mount_sections(page, {'unpaged': True})
    page.evaluate('''() => {
      document.querySelector('main').dataset.lexDetailColumns = '3';
      document.querySelector('.lex-tweaks-paged').lexFitPage();
    }''')
    page.wait_for_timeout(200)
    for name in ('SENSES', 'NAVIGATION'):
        head = page.locator(f'[data-lex-layout-section="{name}"] h3')
        first = page.locator('[data-lex-layout-section="COMBAT"]')
        box = first.bounding_box()
        head.drag_to(first, target_position={'x': 10, 'y': box['height'] - 4})
        page.wait_for_timeout(200)
    deal = lanes(page)
    empty = next((i for i, lane in enumerate(deal) if not lane), -1)
    assert empty >= 0, deal
    lane = page.locator('.lex-tweak-column').nth(empty)
    box = lane.bounding_box()
    # Three pixels into the gap from the empty lane's edge: nearer to it
    # than to any neighbor, and past the old 96px strip vertically.
    aim = box['width'] + 3 if empty < len(deal) - 1 else -3
    point = [box['x'] + aim, box['y'] + 160]
    hit = page.evaluate('([x, y]) => document.elementFromPoint(x, y)?.className', point)
    assert 'lex-tweak-card-grid' in hit and 'lex-tweak-column' not in hit, hit
    # The gap point is grid, so the grid is the drag target: aiming at
    # the lane with an out-of-box offset fails actionability instead.
    grid = page.locator('main .lex-tweak-card-grid').bounding_box()
    page.locator('[data-lex-layout-section="PROPERTIES"] h3').drag_to(
        page.locator('main .lex-tweak-card-grid'),
        target_position={'x': point[0] - grid['x'], 'y': point[1] - grid['y']})
    page.wait_for_timeout(200)
    got = card_order(page)
    assert lanes(page)[empty] == ['PROPERTIES'], lanes(page)
    assert reading_order(page) == got
