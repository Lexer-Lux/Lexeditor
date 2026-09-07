from pathlib import Path

path = Path(__file__).with_name("ui_visual_acceptance.py")
text = path.read_text(encoding="utf-8")
old = '''            simple_heights = [page.locator('.lex-detail-field').nth(i).bounding_box()['height'] for i in range(4)]
            assert max(simple_heights) - min(simple_heights) <= 2, (width, 'property-name fitting changed simple row heights', simple_heights)
'''
new = '''            # Test label fitting with two otherwise identical rows. Different
            # control types legitimately reserve different vertical space (for
            # example a provenance/ref rail), so comparing arbitrary gallery
            # rows would not test the user's requirement. A long PROPERTY NAME
            # must fit by wrapping/scaling without making its row taller.
            page.evaluate("""()=>{
              const make = label => LexeditorUI.detailField({
                label,
                control: LexeditorUI.el('input',{type:'text',value:'x'})
              });
              const panel = LexeditorUI.detailPanel({
                className:'blank-detail', title:'Label Fit Contract',
                icon:LexeditorUI.el('span',{},'L'), identity:'TEST', meta:'Shared label fitting',
                body:[LexeditorUI.detailSection({title:'LABELS',body:[
                  make('SHORT'),
                  make('A DELIBERATELY VERY LONG PROPERTY NAME')
                ]})]
              });
              document.querySelector('#main').replaceChildren(panel);
            }""")
            page.wait_for_timeout(120)
            fit_fields = page.locator('.lex-detail-field')
            simple_heights = [fit_fields.nth(i).bounding_box()['height'] for i in range(2)]
            assert abs(simple_heights[0] - simple_heights[1]) <= 2, (width, 'long property name changed row height', simple_heights)
            long_label = fit_fields.nth(1).locator('.lex-detail-field-label')
            long_fit = long_label.evaluate("e=>({sw:e.scrollWidth,cw:e.clientWidth,sh:e.scrollHeight,ch:e.clientHeight,font:getComputedStyle(e).fontSize})")
            assert long_fit['sw'] <= long_fit['cw'] + 1 and long_fit['sh'] <= long_fit['ch'] + 1, (width, 'long property name did not fit its fixed label lane', long_fit)
'''
if old in text:
    text = text.replace(old, new, 1)
elif new not in text:
    raise SystemExit('simple label-height assertion not found')
path.write_text(text, encoding='utf-8', newline='\n')
