"""Focused regressions for the 2026-09-06 shared/FF8 UI polish batch."""
from __future__ import annotations

from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]


def run(browser_path: str | None = None) -> None:
    from playwright.sync_api import sync_playwright

    browser_path = browser_path or shutil.which("chromium") or shutil.which("chromium-browser")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, **({"executable_path": browser_path} if browser_path else {}))
        try:
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            errors: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.set_content("<base href='http://localhost/'><main id='main'></main>")
            page.add_style_tag(content=(ROOT / "ui/framework.css").read_text(encoding="utf-8"))
            blank = (ROOT / "games/blank/editor.html").read_text(encoding="utf-8")
            blank_css = re.search(r"<style>(.*?)</style>", blank, re.S).group(1)
            page.add_style_tag(content=blank_css)
            page.add_script_tag(content=(ROOT / "ui/framework.js").read_text(encoding="utf-8"))
            page.evaluate("""() => {
              const {el,curveEditor,detailField,provenanceControl,pagedListDetail,columnList}=LexeditorUI;
              const host=document.getElementById('main');
              host.style.cssText='display:grid;gap:18px;width:980px;height:820px';
              const scale=el('input',{type:'number',min:0,max:5,step:.1,value:1});
              const graph=curveEditor({title:'Linear',variables:[{label:'A',control:scale}],
                domain:{min:1,max:100},range:{min:0,max:500},overlayExtrema:true,
                evaluate:level=>level,formula:'Value = Level × A'});
              graph.id='test-graph'; host.append(graph);

              const number=el('input',{id:'number-input',type:'number',min:0,max:100,step:1,value:25});
              const numberSource=provenanceControl({control:number,current:()=>25,vanilla:40,
                references:[{name:'Reference Mod',shortName:'R1',value:35}],apply:()=>{}});
              const numberField=detailField({label:'VALUE',control:numberSource,dataType:'INT',min:0,max:100});
              numberField.id='number-field';
              const fieldsPanel=el('section',{class:'lex-detail lex-detail-panel'},numberField);
              host.append(fieldsPanel);
              const check=el('input',{id:'bool-input',type:'checkbox',checked:false});
              const checkSource=provenanceControl({control:check,current:()=>false,vanilla:true,apply:()=>{}});
              const boolField=detailField({label:'ENABLED',control:checkSource,dataType:'BOOL'});
              boolField.id='bool-field'; fieldsPanel.append(boolField);
              LexeditorUI.refreshReferences(fieldsPanel);

              const internal=el('select',{id:'select-input'},el('option',{value:'alternate'},'Alternate'));
              const internalSource=provenanceControl({control:internal,current:()=> 'alternate',vanilla:'default',
                internal:true,apply:()=>{}});
              const internalField=detailField({label:'SELECT',control:internalSource,dataType:'ENUM'});
              internalField.classList.add('blank-detail'); internalField.id='internal-field';host.append(internalField);

            }""")
            page.wait_for_timeout(500)
            assert not errors, errors

            graph = page.locator("#test-graph")
            assert graph.locator(":scope > .lex-curve-variable-strip").count() == 1
            assert graph.locator(".lex-curve-watermark").count() == 0
            assert graph.locator(".lex-curve-heading-title").inner_text() == "LINEAR"
            assert graph.locator(".lex-curve-formula .lex-curve-variable-a").count() == 1
            assert graph.locator(".lex-curve-path-formula .lex-curve-variable-a").count() == 1
            assert graph.locator(".lex-curve-svg").get_attribute("preserveAspectRatio") == "xMidYMid meet"
            geometry = page.evaluate("""() => {
              const graph=document.querySelector('#test-graph'), plot=graph.querySelector('.lex-curve-plot'),
                    svg=graph.querySelector('.lex-curve-svg'), start=graph.querySelector('.lex-curve-axis-start'),
                    top=graph.querySelector('.lex-curve-axis-top'), ctm=svg.getScreenCTM();
              const p=plot.getBoundingClientRect(), s=svg.getBoundingClientRect(), x=start.getBoundingClientRect(), y=top.getBoundingClientRect();
              return {plotBorder:getComputedStyle(plot).borderTopWidth,
                xBelow:x.top>=s.bottom-1, yLeft:y.right<=s.left+1,
                uniform:Math.abs(Math.abs(ctm.a)-Math.abs(ctm.d))<0.02,
                svgInside:s.left>p.left&&s.top>p.top&&s.right<p.right&&s.bottom<p.bottom};
            }""")
            assert geometry == {"plotBorder":"0px","xBelow":True,"yLeft":True,"uniform":True,"svgInside":True}, geometry
            print("PASS graph strip/title/formula colors/margins/no nested plot border/no non-uniform SVG stretch")

            page.evaluate("document.querySelector('#number-field').classList.add('lex-value-dragging')")
            page.wait_for_timeout(50)
            controls = page.evaluate("""() => {
              const input=document.querySelector('#number-input').getBoundingClientRect();
              const fill=document.querySelector('#number-field .lex-value-fill').getBoundingClientRect();
              const checkbox=document.querySelector('#bool-input').getBoundingClientRect();
              const arrow=document.querySelector('#bool-field .lex-field-boolean-arrow');
              const arrowBox=arrow.getBoundingClientRect(), after=getComputedStyle(arrow,'::after');
              const internal=document.querySelector('#internal-field .lex-source-control-internal');
              const refNode=internal.querySelector('.lex-reference-values'), ref=refNode.getBoundingClientRect();
              return {fillInside:fill.top>=input.top-1&&fill.bottom<=input.bottom+1,
                inputRight:input.right,checkboxRight:checkbox.right,checkboxAligned:Math.abs(checkbox.right-input.right)<1.5,
                arrowShort:arrowBox.width<=48.5,
                arrowHead:parseFloat(after.borderLeftWidth)>=5,
                refNotClipped:refNode.scrollWidth<=refNode.clientWidth+1,refWidth:ref.width,refScroll:refNode.scrollWidth,
                internalWidth:parseFloat(getComputedStyle(internal).getPropertyValue('--lex-internal-reference-width'))};
            }""")
            assert controls["fillInside"] and controls["checkboxAligned"], controls
            assert controls["arrowShort"] and controls["arrowHead"], controls
            assert controls["refNotClipped"] and controls["internalWidth"] >= 5, controls
            print("PASS bounded slider, checkbox edge, boolean arrow head and Blank internal references")

            page.evaluate("""() => {
              const host=document.getElementById('main');
              host.replaceChildren(); host.removeAttribute('style');
              const {el,pagedListDetail,columnList}=LexeditorUI;
              const rows=Array.from({length:48},(_,id)=>({id,name:'Record '+id,value:id}));
              window.lastPageChange=null;
              const paged=pagedListDetail({rows,key:r=>r.id,slots:false,page:0,pageSize:15,noun:'records',
                className:'test-pager',splitKey:'test-pager',rowsKey:'test-pager',fit:{minRowHeight:30},
                selected:0,sync:()=>{},change:next=>{window.lastPageChange=next},
                master:state=>columnList({rows:state.rows,key:r=>r.id,selected:state.selected,select:state.select,
                  template:'80px minmax(120px,1fr)',columns:[{key:'id',label:'ID'},{key:'name',label:'A very long header that must wrap rather than clip'}]}),
                detail:r=>el('div',{class:'lex-detail'},r.name)});
              host.append(paged);
            }""")
            page.wait_for_timeout(500)
            paging = page.evaluate("""() => {
              const root=document.querySelector('#main .lex-paged-list-detail'), master=root.querySelector('.lex-barrelled-master'),
                    pager=root.querySelector('.lex-pager'), label=root.querySelector('.header-label');
              const m=master.getBoundingClientRect(), p=pager.getBoundingClientRect();
              return {noOverlap:m.bottom<=p.top+1, noScroll:master.scrollHeight<=master.clientHeight+1,
                rootTop:root.getBoundingClientRect().top,rootBottom:root.getBoundingClientRect().bottom,
                masterTop:m.top,masterBottom:m.bottom,masterHeight:m.height,pagerTop:p.top,pagerBottom:p.bottom,pagerHeight:p.height,
                headerWrap:getComputedStyle(label).whiteSpace==='normal', pageSize:root.dataset.lexPageSize};
            }""")
            assert paging["noOverlap"] and paging["noScroll"] and paging["headerWrap"], paging
            page.locator("#main .lex-barrelled-master").dispatch_event("wheel", {"deltaY":120,"deltaX":0,"deltaMode":0})
            page.wait_for_timeout(80)
            change = page.evaluate("window.lastPageChange")
            assert change and change["reason"] == "page" and change["page"] == 1, change
            print("PASS pager reserves its own height, avoids vertical scrolling, wraps headers and wheel-turns pages")

        finally:
            browser.close()

    ff8 = (ROOT / "games/ff8/editor.html").read_text(encoding="utf-8")
    assert 'label:"STATUS 1",help:status1?.help?infoHelp(status1.help):null' in ff8
    assert 'label:"STATUS 2",help:status2?.help?infoHelp(status2.help):null' in ff8
    assert '.encounter-slot-table .lex-column-list-head-cell .header-label{white-space:normal' in ff8
    print("PASS FF8 Magic Status help markers and Encounter non-clipping headers are wired")


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv)>1 else None)
