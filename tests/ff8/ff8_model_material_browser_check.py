"""Exercise real WebGL materials without requiring an installed game."""
from pathlib import Path
import os

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]


def main():
    scene = {'positions': [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
             'triangles': [{'indices': [0, 1, 2], 'uv': [[0, 0]] * 3,
                            'texture': -0xFFFFFF - 2,
                            'colors': [[1, 0, 0], [0, 1, 0], [0, 0, 1]]}],
             'textures': []}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 600, 'height': 600})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.route('http://fixture/', lambda route: route.fulfill(body='<html><body></body></html>', content_type='text/html'))
        page.route('**/api/model-scene?*', lambda route: route.fulfill(json=scene))
        page.route('**/assets/texture.png?*', lambda route: route.fulfill(status=404, body='Missing texture'))
        page.goto('http://fixture/')
        page.add_script_tag(path=str(ROOT / 'ui/framework.js'))
        page.add_script_tag(path=str(ROOT / 'plugins/ff8/model_viewer.js'))
        page.add_style_tag(content='.lex-model-stage {position:relative;width:500px;height:500px;background:#222} .lex-model-stage-message {position:relative;z-index:1}')

        def mount():
            page.evaluate('''() => {
                document.querySelector('.lex-model-stage')?.lexDispose();
                window.ready = false; window.failure = null;
                document.body.replaceChildren(FF8ModelViewer({file:'fixture.dat',dataset:'vanilla',label:'Material fixture',
                    onReady:()=>window.ready=true,onError:error=>window.failure=error.message}));
            }''')

        def pixels():
            return page.locator('canvas').evaluate('''canvas => {
                const gl=canvas.getContext('webgl'),pixels=new Uint8Array(canvas.width*canvas.height*4);
                gl.readPixels(0,0,canvas.width,canvas.height,gl.RGBA,gl.UNSIGNED_BYTE,pixels);
                const counts=[0,0,0,0];
                for(let i=0;i<pixels.length;i+=4){if(!pixels[i+3])continue;
                    for(let c=0;c<3;c++)if(pixels[i+c]>100&&pixels[i+c]>2*pixels[i+(c+1)%3]&&pixels[i+c]>2*pixels[i+(c+2)%3])counts[c]++;
                    if(pixels[i]>150&&pixels[i+1]>150&&pixels[i+2]>150)counts[3]++;
                }return counts;
            }''')

        mount()
        page.wait_for_function('window.ready')
        assert min(pixels()[:3]) > 1000, pixels()
        if os.environ.get('LEXEDITOR_MATERIAL_SCREENSHOT'):
            page.screenshot(path=os.environ['LEXEDITOR_MATERIAL_SCREENSHOT'])
        # Existing model scenes omit colours and must retain their white tint.
        del scene['triangles'][0]['colors']
        mount()
        page.wait_for_function('window.ready')
        assert pixels()[3] > 10000, pixels()
        # Failed images must not be accepted or cached as complete previews.
        scene['triangles'][0]['texture'] = 0
        scene['textures'] = [0]
        mount()
        page.wait_for_function('window.failure !== null')
        assert not page.evaluate('window.ready')
        assert page.locator('.lex-model-stage').get_attribute('data-textures-ready') is None
        assert page.get_by_text('Could not load texture 1 for fixture.dat.', exact=True).is_visible()
        assert not errors, errors
        browser.close()
    print('Vertex colours interpolate, existing materials retain their tint, and missing textures report failure.')


if __name__ == '__main__':
    main()
