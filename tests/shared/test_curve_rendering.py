"""Graphs keep mathematical notation and invalid data visible to the user."""
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]


def test_math_curve_resize_and_invalid_divisor():
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1000, "height": 700})
            page.route('http://fixture/**', lambda route: route.fulfill(
                body='<main id="main"></main>', content_type='text/html'))
            page.goto('http://fixture/')
            page.add_style_tag(path=str(ROOT / 'ui/framework.css'))
            page.add_script_tag(path=str(ROOT / 'ui/framework.js'))
            page.evaluate('''() => {
                const UI=LexeditorUI;
                let divisor=2;
                const input=UI.el('input',{type:'number',value:2,
                    oninput:event=>divisor=Number(event.target.value)});
                const curve=UI.curveEditor({title:'HP',
                    variables:[{label:'B',control:input}],
                    range:{min:0,max:100},domain:{min:1,max:10},
                    evaluate:x=>divisor ? x*x/divisor : null,
                    invalidText:'A DIVISOR IS 0',
                    formula:UI.mathFormula('HP(L)=floor(L^2/B)')});
                document.querySelector('main').append(UI.curveGrid(curve));
            }''')
            assert page.locator('.lex-curve-plot math mfrac:visible').count() == 1
            assert page.locator('.lex-curve-plot math msup:visible').count() == 1
            assert page.locator('.lex-curve-svg').get_attribute('preserveAspectRatio') == 'xMidYMid meet'
            page.set_viewport_size({'width': 640, 'height': 700})
            page.locator('.lex-curve-editor').hover()
            page.locator('input').fill('0')
            page.wait_for_timeout(100)
            assert page.locator('.lex-curve-status').inner_text() == 'A DIVISOR IS 0'
            assert page.locator('.lex-curve-line').get_attribute('d') is None
            page.locator('input').fill('4')
            page.wait_for_timeout(100)
            assert page.locator('.lex-curve-status').inner_text() == ''
            assert page.locator('.lex-curve-line').get_attribute('d')
        finally:
            browser.close()


def test_formula_terms_follow_curve_after_resize_and_scale():
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1200, 'height': 900})
            page.route('http://fixture/**', lambda route: route.fulfill(
                body='<main></main>', content_type='text/html'))
            page.goto('http://fixture/')
            page.add_style_tag(path=str(ROOT / 'ui/framework.css'))
            page.add_script_tag(path=str(ROOT / 'ui/framework.js'))
            page.add_style_tag(content='''main{display:block!important}
                .lex-curve-editor,.lex-curve-plot{height:100%;box-sizing:border-box}
                .lex-curve-svg{height:100%;aspect-ratio:auto}''')
            page.evaluate('''()=>{const U=LexeditorUI;
                document.querySelector('main').append(U.curveEditor({title:'HP',
                  domain:{min:1,max:100},range:{min:0,max:11000},evaluate:L=>L*L+L*10,
                  formula:U.mathFormula('HP(L)=floor(A*(L^2/20+L))+10*B+100*C*L+1000*D')}));}''')
            for width, height, zoom in [(650,710,1),(360,500,1),(900,300,.75),(500,600,1.25)]:
                page.evaluate('''([w,h,z])=>{const main=document.querySelector('main');
                    main.style.width=w+'px';main.style.height=h+'px';document.body.style.zoom=z}''', [width,height,zoom])
                page.wait_for_timeout(100)
                measurements = page.locator('.lex-curve-plot').evaluate('''plot=>{
                    const line=plot.querySelector('.lex-curve-line'),svg=plot.querySelector('svg');
                    const ctm=svg.getScreenCTM(),length=line.getTotalLength();
                    const scale=plot.getBoundingClientRect().width/plot.offsetWidth;
                    const points=Array.from({length:3001},(_,i)=>{
                      const p=line.getPointAtLength(i*length/3000);
                      return new DOMPoint(p.x,p.y).matrixTransform(ctm);
                    });
                    return [...plot.querySelectorAll('.lex-curve-math-atom')].map(atom=>{
                      const box=atom.getBoundingClientRect(),m=new DOMMatrix(getComputedStyle(atom).transform);
                      const angle=Math.atan2(m.b,m.a),halfHeight=atom.offsetHeight*scale/2;
                      const anchor={x:(box.left+box.right)/2-Math.sin(angle)*halfHeight,
                        y:(box.top+box.bottom)/2+Math.cos(angle)*halfHeight};
                      let nearest=0,distance=Infinity;
                      points.forEach((p,i)=>{const d=Math.hypot(p.x-anchor.x,p.y-anchor.y);
                        if(d<distance){distance=d;nearest=i}});
                      const before=points[Math.max(0,nearest-5)],after=points[Math.min(3000,nearest+5)];
                      const tangent=Math.atan2(after.y-before.y,after.x-before.x);
                      return {distance:distance/scale,angle:angle*180/Math.PI,
                        error:Math.abs(angle-tangent)*180/Math.PI};
                    });
                }''')
                assert len(measurements) > 10
                assert all(5.5 < item['distance'] < 8.5 for item in measurements), measurements
                assert all(item['error'] < 8 for item in measurements), measurements
                angles = [item['angle'] for item in measurements]
                assert max(angles) - min(angles) > 5, measurements
                assert page.locator('.lex-curve-math-atom mfrac').count() == 1
                assert page.locator('.lex-curve-math-atom msup').count() == 1
                assert page.locator('.lex-curve-plot').evaluate('n=>n.scrollWidth<=n.clientWidth+1')
        finally:
            browser.close()
