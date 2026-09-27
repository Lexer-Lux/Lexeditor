"""Flexible columns retain the minimum needed for their heading and help."""
from test_shared_ui_feedback import page, framework


def test_unitless_zero_grid_minimum_is_valid_inside_heading_math(page):
    framework(page)
    page.evaluate('''()=>{
      const U=LexeditorUI;
      document.querySelector('main').append(U.columnList({
        rows:[{id:'one',kind:'value'}],key:r=>r.id,
        template:'minmax(9rem,1.5fr) minmax(0,1fr)',
        columns:[{key:'id',label:'Record'},
          {key:'kind',label:'Item Type',help:'Fixture field help'}]
      }));
      document.querySelector('.lex-column-list').style.width='240px';
    }''')
    page.evaluate('''async()=>{
      await document.fonts.ready;
      await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
    }''')
    page.wait_for_function('''()=>{
      const table=document.querySelector('.lex-column-list');
      const template=table.style.getPropertyValue('--lex-column-list-template');
      return template.includes('0px') && CSS.supports('grid-template-columns',template);
    }''')
    for heading in page.locator('.lex-column-sort').all():
        fit=heading.evaluate('n=>({width:n.clientWidth,scroll:n.scrollWidth,text:n.textContent,template:n.closest(".lex-column-list").style.cssText})')
        assert fit['scroll']<=fit['width']+1, fit
