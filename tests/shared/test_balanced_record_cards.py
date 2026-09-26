"""Record previews keep balanced rows and accessible selection actions."""
from test_shared_ui_feedback import page, framework


def test_six_record_cards_balance_and_keep_keyboard_actions(page):
    framework(page)
    page.evaluate('''()=>{
      const U=LexeditorUI;
      window.chosen=[];
      document.querySelector('main').append(U.tileGrid(Array.from({length:6},(_,i)=>
        U.recordCard({title:'Enemy '+i,identity:i,
          action:U.el('button',{onclick:()=>chosen.push(i)},'Choose '+i)})),
        {balanced:true,minWidth:150}));
    }''')
    grid=page.locator('.lex-tile-grid')
    for width, columns in ((850,3),(520,3),(350,2),(180,1)):
        grid.evaluate('(e,w)=>e.style.width=w+"px"',width)
        page.wait_for_timeout(80)
        rows=page.locator('.lex-record-card').evaluate_all('''cards=>{
          const rows=new Map();for(const card of cards){const y=card.getBoundingClientRect().top;
          rows.set(y,(rows.get(y)||0)+1);}return [...rows.values()];
        }''')
        assert rows==[columns]*(6//columns), rows
        assert grid.evaluate('e=>e.scrollWidth<=e.clientWidth+1')
    button=page.get_by_role('button',name='Choose 0',exact=True)
    button.focus()
    page.wait_for_timeout(160)
    assert page.locator('.lex-record-card-action').first.evaluate('e=>getComputedStyle(e).opacity')=='1'
    button.press('Enter')
    assert page.evaluate('chosen')==[0]
    # Removing a card recomputes the distribution, not a stale six-card grid.
    grid.evaluate('e=>{e.style.width="520px";e.lastElementChild.remove();}')
    page.wait_for_timeout(80)
    assert len(page.locator('.lex-record-card').all())==5
