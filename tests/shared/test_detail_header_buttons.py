"""Detail header buttons are boxed, tight, and delete is a bin."""
from test_shared_ui_feedback import page, framework

MOUNT = '''() => {
  const U = LexeditorUI;
  const action = (label, icon) => U.el('button', {type: 'button', class: 'lex-header-icon',
    title: label, 'aria-label': label}, icon);
  document.querySelector('main').append(U.detailPanel({title: 'Longsword',
    actions: [action('Duplicate record', U.copyIcon()), action('Delete record', U.removeIcon())]}));
}'''


def test_remove_icon_draws_a_bin(page):
    framework(page)
    page.evaluate(MOUNT)
    svg = page.locator('.lex-header-icon svg').nth(1)
    assert svg.get_attribute('viewBox') == '3 3 18 18'
    assert svg.locator('path').count() == 4


def test_header_buttons_wear_a_box(page):
    framework(page)
    page.evaluate(MOUNT)
    button = page.locator('.lex-header-icon').first
    assert button.evaluate('n => getComputedStyle(n).backgroundColor') != 'rgba(0, 0, 0, 0)'
    assert button.evaluate('n => getComputedStyle(n).borderStyle') != 'none'
    assert button.evaluate('''n => {
      const box = n.getBoundingClientRect();
      return document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2) === n
        || n.contains(document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2));
    }''')


def test_header_actions_sit_tight(page):
    framework(page)
    page.evaluate(MOUNT)
    assert page.locator('.lex-detail-panel-actions').evaluate(
        'n => getComputedStyle(n).gap') == '4px'
