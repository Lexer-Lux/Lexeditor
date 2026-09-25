"""A property name starts at the left edge of its lane.

The names used to end at the lane's right edge, against the control they
belonged to. A short name therefore sat a long way from the lane's left edge
and the column of names was ragged along its left side, which is the side a
reader scans. Each name now begins at the same inset.
"""
from test_shared_ui_feedback import framework, page

BUILD = '''() => {
  const U = LexeditorUI;
  const main = document.querySelector('main');
  main.style.cssText = 'position:absolute;inset:0;padding:20px;width:560px';
  const number = value => U.element('input', {type:'number', value});
  main.replaceChildren(U.detailPanel({title:'Names', body:[
    U.detailField({label:'HP', control:number(4200)}),
    U.detailField({label:'Buy price', control:U.unitField(number(50000),'G')}),
    U.detailField({label:'Sell price', control:U.readonlyField(12500)}),
    U.detailField({label:'Can sell', control:U.element('input', {type:'checkbox', checked:true})}),
    U.detailField({label:'Boost total window (x15)', control:number(22)}),
  ]}));
}'''

MEASURE = '''rows => rows.map(row => {
  const text = row.querySelector('.lex-detail-field-label-text').getBoundingClientRect();
  const lane = row.querySelector('.lex-detail-field-label');
  const box = lane.getBoundingClientRect();
  const style = getComputedStyle(lane);
  return {name: row.querySelector('.lex-detail-field-label-text').textContent.slice(0, 20),
    inset: text.left - (box.left + parseFloat(style.paddingLeft)),
    roomRight: box.right - parseFloat(style.paddingRight) - text.right};
})'''


def test_property_names_start_at_the_left_of_their_lane(page):
    framework(page)
    page.evaluate(BUILD)
    page.wait_for_timeout(300)
    names = page.locator('.lex-detail-field').evaluate_all(MEASURE)
    assert len(names) == 5, names
    assert all(abs(row['inset']) <= 1 for row in names), names
    # A short name leaves the room it does not need on the right.
    assert names[0]['roomRight'] > 10, names
