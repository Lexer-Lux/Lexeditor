"""A game's pointing hand is drawn on top of the tabs and takes no room.

Lexer, 2026-09-27: "INSTEAD OF TAKING THE POINTER FINGER OUT OF THE TABS YOU
NOW MADE IT SO THERE'S A GIANT GAP BETWEEN THEM CREATED BY THE POINTER ... THE
POINTER FINGER IS JUST ON TOP. THAT'S IT." The chosen tab keeps its place; the
hand is drawn over its left edge, above the tabs.
"""
from test_shared_ui_feedback import page, framework


def test_the_hand_sits_on_top_and_opens_no_gap(page):
    framework(page)
    page.evaluate('''()=>{
      const header=document.createElement('header');header.className='lex-shell-header';
      header.style.cssText='--lex-tab-marker-content:"";--lex-tab-marker-width:32px;--lex-tab-border-width:3px;width:900px';
      const nav=document.createElement('nav');nav.style.display='flex';
      for(const [id,label] of [['a','Abilities'],['b','Archives'],['c','Cards']]){
        const b=document.createElement('button');b.dataset.tab=id;b.textContent=label;
        if(id==='b')b.classList.add('active');nav.append(b);}
      header.append(nav);document.querySelector('main').replaceChildren(header);
    }''')
    boxes = page.locator('nav button').evaluate_all('bs=>bs.map(b=>b.getBoundingClientRect().toJSON())')
    hand = page.evaluate('''()=>{const b=document.querySelector('nav button.active'),s=getComputedStyle(b,'::before');
      return {left:parseFloat(s.left),z:s.zIndex,position:s.position}}''')
    # No room is made for the hand: the chosen tab sits right against its neighbour.
    assert abs(boxes[1]['left'] - boxes[0]['right']) <= 1, boxes
    # The hand is drawn over the tab's left edge, above the tabs.
    assert hand['position'] == 'absolute' and int(hand['z']) >= 5, hand
    assert -32 < hand['left'] < 0, hand
