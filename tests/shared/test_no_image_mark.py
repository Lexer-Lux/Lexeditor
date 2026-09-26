"""A missing picture shows the shared "no image" mark, not a broken image.

Lexer: "that no image icon (oh, that should be the default global no image
icon for thumbnails in headers with no thumbnail to show) with the text
[mapid] composed background", and "why not just make a generic global 'no
image' indicator thing for when there's no image".
"""
from test_shared_ui_feedback import page, framework


def test_failed_images_are_replaced_by_the_mark(page):
    framework(page)
    page.evaluate('''() => {
      const U = LexeditorUI, main = document.querySelector('main');
      main.append(U.detailPanel({title: 'Missing art', icon: U.el('img', {src: 'http://fixture/missing.png', alt: 'Enemy'})}));
      main.append(U.el('div', {id: 'explicit', style: 'width:80px;height:80px'}, U.noImage()));
    }''')
    page.wait_for_selector('.lex-detail-panel-icon .lex-no-image-standin')
    icon = page.locator('.lex-detail-panel-icon')
    assert icon.locator('img').evaluate('img => img.hidden') is True
    mark = icon.locator('.lex-no-image')
    assert mark.get_attribute('aria-label') == 'No image: Enemy'
    box = mark.bounding_box()
    slot = icon.bounding_box()
    assert box['width'] > slot['width'] * .8 and box['height'] > slot['height'] * .8, (box, slot)
    assert page.locator('#explicit .lex-no-image').bounding_box()['width'] == 80
