"""A map showing one selected cell must retain its world-grid position."""
from test_shared_ui_feedback import page, framework


def test_sparse_map_cell_uses_explicit_coordinates(page):
    framework(page)
    page.evaluate('''()=>{
      window.picked=null;
      const map=LexeditorUI.imageMap({columns:32,rows:24,ratio:4/3,
        cells:[{id:325,column:5,row:10,label:'Cell 325',selected:true}],
        select:id=>picked=id});
      map.style.width='640px';
      document.querySelector('main').append(map);
    }''')
    cell = page.get_by_role('button', name='Cell 325', exact=True)
    assert cell.evaluate('''n=>{
      const cell=n.getBoundingClientRect(),grid=n.parentElement.getBoundingClientRect();
      return Math.abs(cell.left-grid.left-grid.width*5/32)<1
        && Math.abs(cell.top-grid.top-grid.height*10/24)<1
        && Math.abs(cell.width-grid.width/32)<1
        && Math.abs(cell.height-grid.height/24)<1;
    }''')
    cell.click()
    assert page.evaluate('picked') == 325
