"""Info (?) buttons share one size and stay visible on light backgrounds."""
from test_shared_ui_feedback import framework, page  # noqa: F401  (pytest fixture)


def test_info_help_has_one_size_and_visible_outline(page):
    framework(page)
    page.evaluate('''()=>{
      const U = LexeditorUI, main = document.querySelector('main');
      main.style.background = '#ffffff';
      main.append(
        U.detailField({label: 'Plain property',
          help: U.infoHelp('Plain help'),
          control: U.el('input', {value: 'x'})}),
        U.detailField({label: 'Availability',
          help: U.infoHelp('Availability help'),
          control: U.el('input', {value: 'y'})}),
      );
      const heading = U.el('div', {class: 'lex-column-heading'});
      heading.append(U.el('span', {}, 'Heading'), U.infoHelp('Heading help'));
      main.append(heading);
      main.append(U.toggleRow({label: 'Toggles', toggles: [
        {label: 'First flag', checked: true, help: 'First help'},
        {label: 'Second flag', checked: false, help: 'Second help'},
      ]}));
      const tab = U.el('button', {class: 'lex-subtab-button active'});
      tab.append(U.el('span', {class: 'lex-tab-label'}, 'Tab'), U.infoHelp('Tab help'));
      main.append(tab);
    }''')
    page.wait_for_timeout(100)
    marks = page.locator('.lex-info-help')
    assert marks.count() == 6
    # Toggle help reveals on rail hover by design; hold it open to measure it.
    page.add_style_tag(content='.lex-toggle-rail > .lex-info-help{display:inline-grid !important}')
    boxes = [mark.bounding_box() for mark in marks.all()]
    assert all(box for box in boxes), boxes
    sizes = {(round(box['width']), round(box['height'])) for box in boxes}
    assert len(sizes) == 1, boxes
    width, height = next(iter(sizes))
    assert (width, height) == (16, 16), boxes
    for mark in marks.all():
        style = mark.evaluate('''e => {
          const cs = getComputedStyle(e);
          return {width: cs.width, color: cs.borderTopColor,
            style: cs.borderTopStyle, bw: cs.borderTopWidth};
        }''')
        assert style['style'] != 'none' and float(style['bw'].removesuffix('px')) >= 1, style
        assert style['color'] not in ('rgba(0, 0, 0, 0)', 'transparent'), style
