"""Plain master-list text refits when its column narrows and widens."""
from test_shared_ui_feedback import framework, page


def test_master_identity_fits_at_readable_size_and_grows_back(page):
    framework(page)
    page.evaluate('''()=>{
      const U=LexeditorUI;
      window.list=U.columnList({columns:[{key:'id',label:'Record'}],
        rows:[{id:'TestAnimationMesh'}],key:row=>row.id});
      list.style.width='320px';
      list.style.fontSize='24px';
      document.querySelector('main').append(list);
    }''')
    text=page.locator('.lex-column-cell-text')
    sizes=[]
    for width in (320,150,320):
        page.evaluate('(width)=>list.style.width=width+"px"',width)
        page.wait_for_timeout(250)
        geometry=text.evaluate('''node=>({client:node.clientWidth,scroll:node.scrollWidth,
          font:parseFloat(getComputedStyle(node).fontSize),title:node.title})''')
        assert geometry['scroll']<=geometry['client']+1,geometry
        assert geometry['font']>=9,geometry
        assert geometry['title']=='TestAnimationMesh',geometry
        sizes.append(geometry['font'])
    assert sizes[1]<sizes[0] and sizes[2]==sizes[0],sizes
