"""Master-list icon columns fill their rows.

Lexer (DS1 Items -> Ammo): rows are tall (page-sized, ~50px) but the item
icon in the narrow left column renders tiny, leaving most of the cell
empty. The icon must scale with the row - as large as the row height
allows minus a small padding, keeping its aspect ratio - and the icon
column stays a square cell as the window resizes.
"""
import pytest

from test_shared_ui_feedback import page, framework

# A portrait picture like a DS1 menu icon (160x180), drawn inline so the
# test needs no game files.
ICON_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' width='160' height='180'>"
    "<rect width='160' height='180' fill='#a4824c'/></svg>"
)


def _mount(page):
    framework(page)
    page.evaluate("""(svg) => {
      const U = LexeditorUI, main = document.querySelector('main');
      main.style.height = '90vh';
      const rows = Array.from({length: 16}, (_, id) => ({id, name: 'Record ' + id}));
      const icon = row => {
        if (row.id === 0) return '';  // records without a picture leave the cell empty
        const picture = document.createElement('img');
        picture.src = 'data:image/svg+xml,' + encodeURIComponent(svg);
        picture.alt = '';
        picture.draggable = false;
        return picture;
      };
      main.replaceChildren(U.pagedListDetail({
        rows, key: row => row.id, selected: 0, noun: 'records',
        splitKey: 'icon-fill-check', slots: false, pageSize: 16,
        master: v => U.columnList({rows: v.rows, key: row => row.id, selected: v.selected,
          columns: [
            {key: 'icon', label: '', width: 'var(--lex-fitted-row-height,36px)',
             sortable: false, render: icon},
            {key: 'name', label: 'Name', sortable: true, grow: 1}]}),
        detail: row => U.detailPanel({title: row.name}),
      }));
    }""", ICON_SVG)
    page.wait_for_function(
        "document.querySelector('.lex-column-list-row img')?.naturalWidth > 0")
    page.wait_for_function(
        "getComputedStyle(document.querySelector('.lex-column-list'))"
        ".getPropertyValue('--lex-fitted-row-height').trim() !== ''")
    page.wait_for_timeout(300)  # the fitter settles after fonts load


def _metrics(page):
    return page.evaluate("""() => {
      const fitted = parseFloat(getComputedStyle(
        document.querySelector('.lex-column-list'))
        .getPropertyValue('--lex-fitted-row-height'));
      const rows = [...document.querySelectorAll(
        '.lex-column-list-row:not(.lex-filler-row)')].map(row => {
        const box = row.getBoundingClientRect();
        const cell = row.querySelector('.lex-column-list-cell[data-column-key="icon"]');
        const img = cell.querySelector('img');
        const art = img ? img.getBoundingClientRect() : {height: 0, width: 0};
        const lane = cell.getBoundingClientRect();
        return {row: box.height, icon: art.height,
                iconWidth: art.width, cell: lane.width};
      });
      return {fitted, rows};
    }""")


@pytest.mark.parametrize('height', [850, 550, 400])
def test_icon_fills_its_row_at_window_height(page, height):
    page.set_viewport_size({'width': 1200, 'height': height})
    _mount(page)
    metrics = _metrics(page)
    assert len(metrics['rows']) >= 1, metrics
    for entry in metrics['rows']:
        assert abs(entry['row'] - metrics['fitted']) <= 1, (entry, metrics['fitted'])
        assert abs(entry['cell'] - entry['row']) <= 3, entry
        if entry['icon'] <= 0:
            continue  # the icon-less row keeps an empty but square cell
        # 0.69, not 0.70: sub-pixel rounding puts a 70% floor at 0.6998.
        assert entry['icon'] / entry['row'] >= 0.69, entry
        assert abs(entry['iconWidth'] / entry['icon'] - 160 / 180) < 0.05, entry


def test_icon_keeps_a_fixed_size_without_fitted_rows(page):
    framework(page)
    page.evaluate("""(svg) => {
      const U = LexeditorUI, main = document.querySelector('main');
      const rows = [{id: 0, name: 'Alpha'}, {id: 1, name: 'Beta'}];
      main.replaceChildren(U.columnList({rows, key: row => row.id, selected: 0,
        columns: [
          {key: 'icon', label: '', width: '36px', render: () => {
            const picture = document.createElement('img');
            picture.src = 'data:image/svg+xml,' + encodeURIComponent(svg);
            picture.alt = '';
            return picture;
          }},
          {key: 'name', label: 'Name', grow: 1}]}));
    }""", ICON_SVG)
    page.wait_for_function(
        "document.querySelector('.lex-column-list-row img')?.naturalWidth > 0")
    page.wait_for_timeout(200)
    heights = page.locator('.lex-column-list-row img').evaluate_all(
        'imgs => imgs.map(img => img.getBoundingClientRect().height)')
    assert len(heights) == 2, heights
    assert all(abs(h - 28) < 0.5 for h in heights), heights
