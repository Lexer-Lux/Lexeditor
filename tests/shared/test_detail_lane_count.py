"""The COLUMNS ceiling binds unpaged detail flows, and DS1 fits three lanes.

Lexer could not raise the AI detail past two columns: the divider's
COLUMNS control was ignored for unpaged flows, and the shared 400px card
floor capped his 950px panel at two lanes. The ceiling now binds every
flow with the control, and DS1 sizes its detail cards at 300px (measured
spill-free with zero new clips against the default).
"""
from test_shared_ui_feedback import ROOT, framework, page  # noqa: F401


def mount_lanes(page, width=None):
    framework(page)
    if width is not None:
        page.locator('main').evaluate('(n,w)=>n.style.width=w+"px"', width)
    page.evaluate('''() => {
      const U = LexeditorUI;
      const field = label => U.detailField({label, property: label.toLowerCase(),
        control: U.el('input', {value: label})});
      const wrap = U.el('div', {id: 'lanes-wrap'});
      wrap.append(U.detailPanel({title: 'Record', paginate: {unpaged: true}, body: [
        U.detailSection({title: 'One', body: [field('Alpha'), field('Beta')]}),
        U.detailSection({title: 'Two', body: [field('Gamma'), field('Delta')]}),
        U.detailSection({title: 'Three', body: [field('Epsilon'), field('Zeta')]}),
        U.detailSection({title: 'Four', body: [field('Eta'), field('Theta')]}),
      ]}));
      document.querySelector('main').replaceChildren(wrap);
    }''')
    page.wait_for_timeout(200)


def lane_count(page):
    return page.locator('.lex-tweak-column').count()


def refit(page):
    page.evaluate("document.querySelector('.lex-tweaks-paged').lexFitPage()")
    page.wait_for_timeout(200)


def test_columns_control_caps_unpaged_lanes(page):
    mount_lanes(page)
    assert lane_count(page) >= 2
    page.evaluate("document.querySelector('#lanes-wrap').dataset.lexDetailColumns = '1'")
    refit(page)
    assert lane_count(page) == 1
    page.evaluate("document.querySelector('#lanes-wrap').dataset.lexDetailColumns = '2'")
    refit(page)
    assert lane_count(page) == 2
    page.evaluate("delete document.querySelector('#lanes-wrap').dataset.lexDetailColumns")
    refit(page)
    assert lane_count(page) >= 2


def test_ds1_detail_fits_three_lanes_at_user_width(page):
    mount_lanes(page, 1000)
    assert lane_count(page) == 2
    page.add_style_tag(path=str(ROOT / 'plugins/ds1/editor.css'))
    page.wait_for_timeout(300)
    refit(page)
    assert lane_count(page) == 3
