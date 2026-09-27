"""A game's pointing hand stands outside the chosen tab, in room of its own.

Lexer, 2026-09-27, after the hand kept coming back inside FF8's tabs: never
draw it inside a tab. The chosen tab leaves a gap as wide as the hand on its
left, and the hand is drawn in that gap, not over the tab or its neighbour.
"""
from test_shared_ui_feedback import page, framework


def test_the_chosen_tab_leaves_the_hand_its_own_room(page):
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
    before = page.evaluate('''()=>{const b=document.querySelector('nav button.active'),s=getComputedStyle(b,'::before');
      return {right:s.right,left:s.left}}''')
    room = boxes[1]['left'] - boxes[0]['right']
    assert room >= 32, room
    # The hand's left edge lies at least its own width left of the tab.
    assert float(before['left'].rstrip('px')) <= -32, before
