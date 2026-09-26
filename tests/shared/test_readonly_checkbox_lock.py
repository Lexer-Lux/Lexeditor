"""A read-only checkbox shows its lock beside the box, not over the tick.

The lock is right-aligned inside a read-only value box. A checkbox is smaller
than that margin, so the lock was drawn on top of the tick (reported on FF7R,
true of every game). It now stands just left of the box, and the leader arrow
stops short of it.
"""
from test_shared_ui_feedback import page, framework


def test_lock_stands_between_arrow_and_checkbox(page):
    framework(page)
    page.evaluate('''() => {
      const U = LexeditorUI, box = U.el('div', {style: 'width:600px'});
      document.querySelector('main').append(box);
      box.append(U.detailField({label: 'Locked on', showType: true,
        control: U.el('input', {type: 'checkbox', checked: true, disabled: true})}));
      box.append(U.detailField({label: 'Locked num', showType: true,
        control: U.el('input', {type: 'number', value: 4, readOnly: true})}));
    }''')
    page.wait_for_timeout(300)
    geometry = page.evaluate('''() => {
      const fields = document.querySelectorAll('.lex-detail-field');
      const rect = node => node.getBoundingClientRect();
      const [flag, number] = fields;
      const lock = rect(flag.querySelector('.lex-field-readonly-lock'));
      const box = rect(flag.querySelector('input[type=checkbox]'));
      const arrow = rect(flag.querySelector('.lex-field-boolean-arrow'));
      const numberLock = rect(number.querySelector('.lex-field-readonly-lock'));
      const numberBox = rect(number.querySelector('input'));
      return {lockLeft: lock.left, lockRight: lock.right, boxLeft: box.left,
        arrowRight: arrow.right, lockMid: (lock.top + lock.bottom) / 2, boxMid: (box.top + box.bottom) / 2,
        numberLockRight: numberLock.right, numberBoxRight: numberBox.right, numberBoxLeft: numberBox.left};
    }''')
    assert geometry['lockRight'] <= geometry['boxLeft'] - 2, geometry
    assert geometry['arrowRight'] <= geometry['lockLeft'] - 2, geometry
    assert abs(geometry['lockMid'] - geometry['boxMid']) <= 2, geometry
    # A value box keeps its lock inside, against the right edge.
    assert geometry['numberBoxLeft'] < geometry['numberLockRight'] <= geometry['numberBoxRight'], geometry
