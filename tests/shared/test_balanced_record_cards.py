"""Record previews keep balanced rows and accessible selection actions."""
from test_shared_ui_feedback import page, framework


def test_record_images_stay_inside_the_card_at_different_aspect_ratios(page):
    framework(page)
    page.evaluate('''()=>{
      const U=LexeditorUI;
      const cards=[[128,256],[256,128]].flatMap(([w,h])=>[false,true].map(linked=>{
        const image=U.el('img',{src:'data:image/svg+xml,'+encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}"><rect width="100%" height="100%" fill="cyan"/></svg>`)});
        return U.recordCard({title:'Texture',image:linked?U.el('a',{href:'#'},image):image,body:U.el('select',{},U.el('option',{},'Palette 1'))});
      }));
      document.querySelector('main').append(U.tileGrid(cards,{balanced:true,minWidth:150}));
    }''')
    page.wait_for_function('Array.from(document.images).every(image=>image.complete&&image.naturalWidth>0)')
    for width in (850, 350):
        page.locator('.lex-tile-grid').evaluate('(grid,width)=>grid.style.width=width+"px"', width)
        page.wait_for_timeout(80)
        bounds = page.locator('.lex-record-card').evaluate_all('''cards=>cards.map(card=>{
          const outer=card.getBoundingClientRect(),image=card.querySelector('img').getBoundingClientRect();
          return {card:outer.height,image:image.height,fits:image.top>=outer.top&&image.bottom<=outer.bottom+1};
        })''')
        assert all(item['fits'] for item in bounds), bounds


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


def test_record_holder_accepts_arbitrary_counts_and_live_changes(page):
    framework(page)
    page.evaluate('''()=>{
      const U=LexeditorUI;
      window.makeCard=i=>U.recordCard({title:'Record '+i,identity:i});
      document.querySelector('main').append(U.tileGrid([],{balanced:true,minWidth:150}));
    }''')
    grid=page.locator('.lex-tile-grid')
    def assert_rows(expected):
        page.wait_for_function('''expected=>{
          const grid=document.querySelector('.lex-tile-grid'), rows=new Map();
          for(const card of grid.children){
            if(card.hidden)continue;
            const y=card.getBoundingClientRect().top;
            rows.set(y,(rows.get(y)||0)+1);
          }
          return JSON.stringify([...rows.values()])===JSON.stringify(expected);
        }''',arg=expected)
        assert grid.evaluate('e=>e.scrollWidth<=e.clientWidth+1')

    grid.evaluate('e=>e.style.width="850px"')
    for count, rows in ((0,[]),(1,[1]),(2,[2]),(3,[3]),(4,[4]),(5,[5]),
                        (6,[3,3]),(7,[4,3]),(11,[4,4,3]),(17,[5,5,5,2])):
        grid.evaluate('(e,n)=>e.replaceChildren(...Array.from({length:n},(_,i)=>makeCard(i)))',count)
        assert_rows(rows)
    grid.evaluate('e=>e.style.width="180px"')
    assert_rows([1]*17)
    grid.evaluate('e=>{e.style.width="850px";e.replaceChildren(...Array.from({length:5},(_,i)=>makeCard(i)));}')
    assert_rows([5])
    grid.evaluate('e=>e.append(makeCard(5))')
    assert_rows([3,3])
    grid.evaluate('e=>e.lastElementChild.hidden=true')
    assert_rows([5])
    grid.evaluate('e=>e.lastElementChild.hidden=false')
    assert_rows([3,3])
    grid.evaluate('e=>e.lastElementChild.remove()')
    assert_rows([5])
