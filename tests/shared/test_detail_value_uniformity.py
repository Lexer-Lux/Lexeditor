"""Detail values share one size: borderline faces keep full size, boxes match.

DS1 AI shrank its Logic & goals values to 13.67px while every other
section stayed 15px: the select-face reserve counted padding-right
shadowed under the arrow plus a 22px arrow zone, 16px over the measured
room, so "Walk to Target" shrank for touching nothing. Boxes differed
too: inputs 26.3px, selects 28px, boolean boxes 26px. Faces now fit
against pad-left plus the measured 15px arrow zone, and every
single-line value box stands 26px.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_shared_ui_feedback import framework, page  # noqa: F401,E402

BUILD = """() => {
  const U = LexeditorUI;
  document.documentElement.dataset.lexBooleanStyle = 'box';
  const main = document.querySelector('main');
  main.style.cssText = 'display:block;';
  const host = U.el('div', {style: 'width:146px;font-size:15px;font-family:"Palatino Linotype","Book Antiqua",Palatino,Georgia,serif;'});
  const section = U.el('div', {class: 'lex-detail-section'});
  const input = U.el('input', {type: 'text', value: '5', style: 'width:100%;'});
  const select = U.el('select', {style: 'width:100%;'}, U.el('option', {}, 'Walk to Target'));
  section.append(U.el('div', {class: 'lex-detail-field-control'}, input),
    U.el('div', {class: 'lex-detail-field-control'}, select));
  const boolean = U.el('div', {class: 'lex-boolean-field'},
    U.el('div', {class: 'lex-detail-field-control'}, U.el('input', {type: 'checkbox'})));
  host.append(section, boolean);
  main.replaceChildren(host);
  U.autoFitControlText(input);
  U.autoFitControlText(select);
}"""

STATE = """() => {
  const host = document.querySelector('main > div');
  const input = host.querySelector('.lex-detail-section input');
  const select = host.querySelector('.lex-detail-section select');
  const box = host.querySelector('.lex-boolean-field input');
  const style = getComputedStyle(select);
  const canvas = document.createElement('canvas');
  const context = canvas.getContext('2d');
  context.font = `${style.fontStyle} ${style.fontWeight} 15px ${style.fontFamily}`;
  const ink = context.measureText('Walk to Target').width;
  const padLeft = parseFloat(style.paddingLeft), padRight = parseFloat(style.paddingRight);
  const border = parseFloat(style.borderLeftWidth) + parseFloat(style.borderRightWidth);
  return {
    // Self-validating premise: the ink fits the corrected reserve but
    // not the old one, so only the fix keeps full size.
    oldRoom: select.clientWidth - padLeft - padRight - border - 22,
    newRoom: select.clientWidth - padLeft - border - 15,
    ink,
    inputFont: getComputedStyle(input).fontSize,
    selectFont: getComputedStyle(select).fontSize,
    heights: [input, select, box].map(n => n.getBoundingClientRect().height),
  };
}"""


def test_borderline_face_keeps_full_size_and_boxes_match(page):
    framework(page)
    page.evaluate(BUILD)
    page.evaluate("()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(()=>requestAnimationFrame(r))))")
    page.wait_for_timeout(300)
    state = page.evaluate(STATE)
    assert state['oldRoom'] < state['ink'] <= state['newRoom'], state
    assert state['inputFont'] == '15px', state
    assert state['selectFont'] == '15px', state
    assert state['heights'] == [26, 26, 26], state
