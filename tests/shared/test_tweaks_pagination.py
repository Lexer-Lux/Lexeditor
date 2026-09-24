"""R2-1: RDR2-shaped Tweaks groups stay reachable through the shared pager.

The harness used to regex an inline <style> block out of
plugins/rdr2/editor.html, but that file now links editor.css instead, so the
match was None and the harness died with TypeError before checking anything.
The pager itself only knew how to split detail sections, so RDR2 settings
cards (sections of subs of fields) flip-flopped between paginated,
unpaginated and unreachable. Both are locked in here: the harness reads the
real CSS files, and settings cards split between subs — with one long sub
splitting between its own fields — so every control stays reachable.
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]


def test_harness_reads_real_css_files():
    harness = (ROOT / 'tests/shared/verify_tweaks_pagination.py').read_text(encoding='utf-8')
    assert 'editor.css' in harness
    assert 're.search' not in harness
    assert '<style>' not in (ROOT / 'plugins/rdr2/editor.html').read_text(encoding='utf-8')


def test_settings_cards_split_and_stay_reachable():
    fixture = """() => {
      const u = LexeditorUI;
      const host = document.createElement('div');
      let cards = '';
      for (let i = 0; i < 5; i++) {
        let subs = '';
        for (let s = 0; s < 4; s++) {
          const rows = (i === 2 && s === 1) ? 10 : 2;
          let fields = '';
          for (let f = 0; f < rows; f++) {
            fields += `<div class="settings-field">`
              + `<div class="settings-field-label">Setting ${i}-${s}-${f}</div>`
              + `<div class="settings-field-control"><input aria-label="Setting ${i}-${s}-${f}" value="${i}-${s}-${f}"></div>`
              + `</div>`;
          }
          subs += `<div class="settings-sub"><h3>Sub ${i}-${s}</h3><div class="settings-fields">${fields}</div></div>`;
        }
        cards += `<section class="settings-section" data-card="${i}"><h2>Group ${i}</h2><div class="settings-subs">${subs}</div></section>`;
      }
      host.innerHTML = cards;
      document.querySelector('main').append(u.settingsColumns([...host.children], {columnMajor: true, strictColumns: true}));
    }"""
    expected = {f'Setting {i}-{s}-{f}' for i in range(5) for s in range(4)
                for f in range(10 if (i == 2 and s == 1) else 2)}
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 800, 'height': 600})
            page.route('http://fixture/**', lambda r: r.fulfill(body='<html></html>', content_type='text/html'))
            page.goto('http://fixture/')
            css = (ROOT / 'ui/framework.css').read_text(encoding='utf-8')
            rdr_css = (ROOT / 'plugins/rdr2/editor.css').read_text(encoding='utf-8')
            page.set_content('<style>' + rdr_css + css + '</style>'
                             '<header class="lex-shell-header" style="height:130px;flex-shrink:0">Tweaks</header>'
                             '<main></main>')
            page.add_script_tag(path=str(ROOT / 'ui/framework.js'))
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.evaluate(fixture)
            page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
            assert not errors, errors
            page.get_by_label('Setting 0-0-0', exact=True).fill('changed')
            seen, labels = set(), set()
            while True:
                seen.update(page.locator('[data-card]:visible')
                            .evaluate_all('(nodes)=>nodes.map(n=>+n.dataset.card)'))
                for label in page.locator('[data-card]:visible input').evaluate_all(
                        '(nodes)=>nodes.map(n=>n.getAttribute("aria-label"))'):
                    field = page.locator('[data-card]:visible').locator(f'input[aria-label="{label}"]')
                    field.scroll_into_view_if_needed()
                    box = field.bounding_box()
                    assert box['y'] >= 0 and box['y'] + box['height'] <= 600, (label, box)
                    labels.add(label)
                pager = page.locator('.lex-tweaks-pages').bounding_box()
                assert pager['y'] + pager['height'] <= 601, pager
                if not page.get_by_role('button', name='Next page', exact=True).is_enabled():
                    break
                page.get_by_role('button', name='Next page', exact=True).click()
            assert seen == set(range(5)), seen
            assert labels == expected, len(labels)
            assert page.get_by_label('Setting 0-0-0', exact=True).input_value() == 'changed'
            assert not errors, errors
        finally:
            browser.close()
