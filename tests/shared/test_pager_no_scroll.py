"""A paged panel never scrolls: pages split to fit, pins stay in the row.

paginateSettings fills each page until one more card would overflow it, and
an inline detail flow splits a section too tall for the page between its
rows. A scrollbar beside the pager means the split was vetoed or skipped.
The hover pin likewise belongs at the box's corner inside its row; past the
row its pixels read as overflow and veto the split that would remove the
scrollbar.
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]


def boot(page):
    page.route('http://fixture/**', lambda r: r.fulfill(body='<html></html>', content_type='text/html'))
    page.goto('http://fixture/')
    css = (ROOT / 'ui/framework.css').read_text(encoding='utf-8')
    page.set_content('<style>' + css + '</style><main style="height:500px"></main>')
    page.add_script_tag(path=str(ROOT / 'ui/framework.js'))
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    return errors


def settle(page):
    page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(()=>requestAnimationFrame(r))))')


def test_inline_pages_split_and_never_scroll():
    fixture = """() => {
      const rows = count => Array.from({length: count}, (_, i) =>
        `<div class="lex-detail-field" style="height:44px">`
        + `<div class="lex-detail-field-label">R${i}</div>`
        + `<div class="lex-detail-field-control"><input value="${i}" aria-label="R${i}"></div></div>`).join('');
      const section = (title, count) =>
        `<section class="lex-detail-section" aria-label="${title}"><h2 class="lex-detail-section-title">${title}</h2>`
        + `<div class="lex-detail-section-content">${rows(count)}</div></section>`;
      const content = document.createElement('div');
      content.innerHTML = section('Tall', 20) + section('Short', 3);
      document.querySelector('main').append(LexeditorUI.paginateSettings(content, {inline: true}));
    }"""
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 800, 'height': 600})
            errors = boot(page)
            page.evaluate(fixture)
            settle(page)
            assert not errors, errors
            state = page.evaluate("""() => {
              const root = document.querySelector('.lex-tweaks-paged');
              const scroll = root.querySelector('.lex-tweaks-scroll');
              return {pages: root.lexPaging().starts.length,
                      continued: root.querySelectorAll('.lex-detail-section-continued').length,
                      labels: [...root.querySelectorAll('.lex-detail-section[aria-label]')]
                        .map(node => node.getAttribute('aria-label')),
                      client: scroll.clientHeight, height: scroll.scrollHeight};
            }""")
            assert state['pages'] > 1, state
            assert state['continued'] >= 1, state
            assert state['labels'].count('Tall') == 1, state
            assert all(label in ('Tall', 'Short') or label.endswith(' (continued)')
                       for label in state['labels']), state
            assert state['height'] <= state['client'] + 1, state
            for _ in range(state['pages'] - 1):
                page.locator(".lex-tweaks-pages button[aria-label='Next page']").click()
                settle(page)
                metrics = page.evaluate("""() => {
                  const scroll = document.querySelector('.lex-tweaks-scroll');
                  return {client: scroll.clientHeight, height: scroll.scrollHeight};
                }""")
                assert metrics['height'] <= metrics['client'] + 1, metrics
            assert not errors, errors
        finally:
            browser.close()


def test_detail_pin_stays_inside_its_row():
    fixture = """() => {
      const u = LexeditorUI;
      const input = document.createElement('input');
      input.value = '12';
      const control = u.provenanceControl({control: input, current: 12, vanilla: 12});
      const pin = document.createElement('button');
      pin.className = 'lex-column-pin';
      pin.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18"><circle cx="12" cy="12" r="10"/></svg>';
      document.querySelector('main').append(u.detailField({label: 'PINNED', control, pin}));
    }"""
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 800, 'height': 600})
            errors = boot(page)
            page.evaluate(fixture)
            settle(page)
            assert not errors, errors
            pin = page.evaluate("""() => {
              const row = document.querySelector('.lex-detail-field');
              const ghost = row.querySelector('.lex-column-pin');
              const rowBox = row.getBoundingClientRect(), pinBox = ghost.getBoundingClientRect();
              return {pinRight: pinBox.right, rowRight: rowBox.right,
                      rowScroll: row.scrollWidth, rowClient: row.clientWidth};
            }""")
            assert pin['pinRight'] <= pin['rowRight'] + 1, pin
            assert pin['rowScroll'] <= pin['rowClient'] + 1, pin
        finally:
            browser.close()
