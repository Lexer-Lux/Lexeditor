"""A pin has to be big enough to hit and to read.

The pin is the mark that puts a property into the table beside the record. It
sits in the corner of a field control and stays hidden until the row is
hovered, so it is small by design - but the drawn mark must not be smaller than
the text it annotates, or it reads as a speck.
"""
import pytest

from test_shared_ui_feedback import framework, page


def mount_pinned_field(page, pinned):
    page.evaluate("""pinned => {
      const U = LexeditorUI;
      window.__prefs = U.columnPreferences('pin-size-check',
        [{key: 'weight', label: 'Weight'}], () => {});
      const pin = window.__prefs.pinButton('weight', 'Weight');
      if (pinned) pin.classList.add('pinned');
      const panel = U.detailPanel({title: 'Record', body: [
        U.detailField({label: 'Weight', pin,
          control: U.el('input', {type: 'number', value: 42})})]});
      document.querySelector('main').append(panel);
      window.__pin = panel.querySelector('.lex-column-pin');
    }""", pinned)
    page.wait_for_timeout(250)


MEASURE = """()=>{
  const pin = window.__pin;
  const glyph = pin.querySelector('svg');
  const box = pin.getBoundingClientRect();
  const drawn = glyph.getBoundingClientRect();
  const control = pin.closest('.lex-detail-field-control').getBoundingClientRect();
  const field = pin.closest('.lex-detail-field').getBoundingClientRect();
  const label = pin.closest('.lex-detail-field').querySelector('.lex-detail-field-label-text').getBoundingClientRect();
  return {
    box: {w: box.width, h: box.height},
    glyph: {w: drawn.width, h: drawn.height},
    withinField: box.right <= field.right + 1 && box.left >= field.left - 1 &&
      box.bottom <= field.bottom + 1,
    clearOfLabel: box.left >= label.right - 1 || box.bottom <= label.top + 1,
    fontSize: parseFloat(getComputedStyle(pin).fontSize),
    insideControl: box.right <= control.right + 2,
    opacity: Number(getComputedStyle(pin).opacity),
  };
}"""


@pytest.mark.parametrize("pinned", [False, True])
def test_the_drawn_pin_is_not_smaller_than_its_text(page, pinned):
    framework(page)
    mount_pinned_field(page, pinned)
    page.locator(".lex-detail-field").hover()
    page.wait_for_timeout(200)
    metrics = page.evaluate(MEASURE)
    assert metrics["glyph"]["h"] >= metrics["fontSize"], metrics
    assert metrics["glyph"]["w"] >= metrics["fontSize"], metrics
    assert metrics["box"]["h"] >= metrics["glyph"]["h"], metrics
    assert metrics["clearOfLabel"], metrics
    assert metrics["opacity"] > 0.5, metrics
