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
                        tangent:tangent*180/Math.PI,
                        error:Math.abs(angle-tangent)*180/Math.PI};
                    });
                }''')
                assert len(measurements) > 10
                assert all(5.5 < item['distance'] < 8.5 for item in measurements), measurements
                # Each term takes the slope under it, except where the slope is
                # steeper than the angle a piece of text can be read at: there
                # it stops at the bound instead of turning onto its side.
                for item in measurements:
                    if abs(item['tangent']) <= 40:
                        assert item['error'] < 8, item
                    else:
                        assert abs(item['angle']) <= 40.01, item
                # The fixture's own curve is steeper than the bound nearly
                # everywhere, so its terms all rest at the bound; what has to
                # vary for this check to mean anything is the slope they are
                # being compared against.
                tangents = [item['tangent'] for item in measurements]
                assert max(tangents) - min(tangents) > 5, measurements
                assert page.locator('.lex-curve-math-atom mfrac').count() == 1
                assert page.locator('.lex-curve-math-atom msup').count() == 1
                assert page.locator('.lex-curve-plot').evaluate('n=>n.scrollWidth<=n.clientWidth+1')
        finally:
            browser.close()


def test_the_least_and_greatest_values_read_in_the_accent_and_the_equation_is_legible():
    """The graph's own numbers are graph ink, and its equation can be read.

    The curve's minimum and maximum were plain body text with no rule of their
    own, so they read as grey labels between other words, and the equation
    drawn over the line was set at 11px.
    """
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
                const curve=UI.curveEditor({title:'HP', range:{min:0,max:100},
                    domain:{min:1,max:10}, evaluate:x=>x*x,
                    formula:UI.mathFormula('HP(L)=L^2')});
                document.querySelector('main').append(UI.curveGrid(curve));
            }''')
            page.wait_for_timeout(200)
            measured = page.evaluate('''() => {
                const accent=getComputedStyle(document.documentElement)
                    .getPropertyValue('--lex-accent').trim();
                const probe=document.createElement('span');
                probe.style.color=accent;
                document.body.append(probe);
                const wanted=getComputedStyle(probe).color;
                probe.remove();
                const minimum=getComputedStyle(document.querySelector('.lex-curve-minimum')).color;
                const maximum=getComputedStyle(document.querySelector('.lex-curve-maximum')).color;
                const formula=getComputedStyle(document.querySelector('.lex-curve-path-formula'));
                return {wanted, minimum, maximum,
                    formulaSize: parseFloat(formula.fontSize)};
            }''')
            assert measured['minimum'] == measured['wanted'], measured
            assert measured['maximum'] == measured['wanted'], measured
            assert measured['formulaSize'] >= 12.5, measured
        finally:
            browser.close()


def test_the_end_numbers_stay_off_the_line_and_the_equation_stays_readable():
    """The two things a steep curve broke on the character screens.

    The least and greatest values were lifted straight up from the curve, so on
    a steep line they drifted back onto it - worst where the curve climbs into
    the top corner of the plot, which is what an XP curve does. And each term of
    the equation took the local slope with no bound, so a curve that climbs and
    comes back down turned the formula into a seesaw: on the arc below the
    steepest term was 83 degrees over from level.
    """
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 2048, "height": 1100})
            page.route("http://fixture/**", lambda route: route.fulfill(
                body="<main id='mount'></main>", content_type="text/html"))
            page.goto("http://fixture/")
            page.add_style_tag(path=str(ROOT / "ui/framework.css"))
            page.add_style_tag(content="#mount{display:grid;"
                               "grid-template-columns:repeat(3,minmax(0,1fr));"
                               "gap:12px;height:900px}")
            page.add_script_tag(path=str(ROOT / "ui/framework.js"))
            page.evaluate("""()=>{
                const xp=(level,a,b)=>10*(level-1)*a+Math.floor((level-1)**2*b/256);
                const shapes=[
                  ['XP', l=>xp(l,20,255), 0, xp(100,20,255)],
                  ['ARC', l=>Math.max(0,255-2*(l-6)**2), 0, 255],
                  ['STEEP', l=>Math.min(255,3*l*l), 0, 300],
                ];
                const mount=document.querySelector('#mount');
                for (const [title,evaluate,min,max] of shapes) {
                  mount.append(LexeditorUI.curveEditor({title,overlayExtrema:true,
                    domain:{min:1,max:100},range:{min,max},evaluate,
                    formula:LexeditorUI.mathFormula('F(L)=A*(L-1)+B*(L-1)^2/256')}));
                }
            }""")
            page.wait_for_timeout(600)
            measured = page.evaluate("""()=>[...document.querySelectorAll('.lex-curve-editor')]
                .map(card=>{
              const plot=card.querySelector('.lex-curve-plot');
              const line=plot.querySelector('.lex-curve-line');
              const matrix=plot.querySelector('svg').getScreenCTM();
              const length=line.getTotalLength();
              const points=[];
              for(let i=0;i<=600;i+=1){
                const p=line.getPointAtLength(i*length/600);
                points.push(new DOMPoint(p.x,p.y).matrixTransform(matrix));
              }
              const inside=(px,py,corners)=>{
                let hit=false;
                for(let i=0,j=3;i<4;j=i,i+=1){
                  const [xi,yi]=corners[i],[xj,yj]=corners[j];
                  if(((yi>py)!==(yj>py))&&(px<(xj-xi)*(py-yi)/(yj-yi)+xi))hit=!hit;
                }
                return hit;};
              const labels=[...card.querySelectorAll('.lex-curve-range-value')].map(node=>{
                const own=node.getBBox();
                const corners=[[own.x,own.y],[own.x+own.width,own.y],
                  [own.x+own.width,own.y+own.height],[own.x,own.y+own.height]]
                  .map(([x,y])=>{const p=new DOMPoint(x,y).matrixTransform(
                    node.getScreenCTM());return [p.x,p.y];});
                return {text:node.textContent,
                  hits:points.filter(p=>inside(p.x,p.y,corners)).length};});
              const angles=[...card.querySelectorAll('.lex-curve-math-atom')].map(node=>{
                const m=new DOMMatrix(getComputedStyle(node).transform);
                return Math.abs(Math.atan2(m.b,m.a)*180/Math.PI);});
              return {title:card.dataset.curveTitle,labels,
                maxAngle:angles.length?Math.max(...angles):0};})""")
            assert len(measured) == 3, measured
            for card in measured:
                assert len(card['labels']) == 2, card
                for label in card['labels']:
                    assert label['hits'] == 0, card
                assert card['maxAngle'] <= 40.0001, card
        finally:
            browser.close()
