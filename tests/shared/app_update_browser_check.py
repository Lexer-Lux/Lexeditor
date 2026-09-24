"""Headless Home update flow; never replaces the real installation."""
import functools
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile
import threading
from playwright.sync_api import sync_playwright
from global_browser_check import ROOT, Handler, STUB, load_page


def main(output):
    output.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=str(ROOT)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            for width, height in ((900, 620), (1600, 900)):
                # No release: Home shows no update button at all.
                page = browser.new_page(viewport={"width": width, "height": height})
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.add_init_script(STUB)
                page.add_init_script("window.pywebview.api.app_update_status=async()=>({available:false,tag:'v1.2',"
                                     "message:'This install is newer than the latest published release.'})")
                load_page(page, f'http://127.0.0.1:{server.server_port}', '/ui/chooser.html')
                page.locator('#loading-screen').wait_for(state='hidden')
                page.wait_for_timeout(200)
                assert page.get_by_role('button', name='Update Lexeditor', exact=True).count() == 0
                assert not errors, errors
                page.close()

                # A release: the button sits bottom-right and offers the install.
                page = browser.new_page(viewport={"width": width, "height": height})
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.add_init_script(STUB)
                page.add_init_script("window.__installs=0;"
                                     "window.pywebview.api.app_update_status=async()=>({available:true,tag:'v9.0',"
                                     "message:'A new release is ready to install.'});"
                                     "window.pywebview.api.install_app_update=async()=>{__installs++;"
                                     "throw Error('Save or discard editor changes before updating Lexeditor.')}")
                load_page(page, f'http://127.0.0.1:{server.server_port}', '/ui/chooser.html')
                page.locator('#loading-screen').wait_for(state='hidden')
                button = page.get_by_role('button', name='Update Lexeditor', exact=True)
                button.wait_for()
                box = button.bounding_box()
                # Pinned to the bottom-right corner, whatever the window size.
                assert box and width - (box['x'] + box['width']) <= 40 and height - (box['y'] + box['height']) <= 40, box
                button.click()
                page.get_by_role('button', name='INSTALL v9.0', exact=True).click()
                # Unsaved editor changes refuse the install, and say why.
                page.get_by_text('Save or discard editor changes before updating Lexeditor.', exact=True).wait_for()
                assert page.evaluate('__installs') == 1
                page.get_by_role('button', name='CLOSE', exact=True).click()
                page.screenshot(path=str(output / f'home-{width}.png'))

                # Offline at the moment of the click: say so, and hide the button,
                # since there is no longer a release it can vouch for.
                page.evaluate("window.pywebview.api.app_update_status=async()=>{throw Error('Offline')};void 0")
                button.click()
                page.get_by_text('Offline', exact=True).wait_for()
                page.get_by_role('button', name='CLOSE', exact=True).click()
                assert button.is_hidden()

                # No newer release by the time of a click: no downgrade is offered.
                page.close()
                page = browser.new_page(viewport={"width": width, "height": height})
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.add_init_script(STUB)
                page.add_init_script("window.__checks=0;window.pywebview.api.app_update_status=async()=>"
                                     "(++__checks===1?{available:true,tag:'v9.0',message:'Ready.'}"
                                     ":{available:false,tag:'v1.2',message:'This install is newer than the latest published release.'})")
                load_page(page, f'http://127.0.0.1:{server.server_port}', '/ui/chooser.html')
                page.locator('#loading-screen').wait_for(state='hidden')
                button = page.get_by_role('button', name='Update Lexeditor', exact=True)
                button.wait_for()
                button.click()
                page.wait_for_timeout(200)
                assert page.get_by_role('button', name='INSTALL v1.2', exact=True).count() == 0
                assert button.is_hidden()
                assert not errors, errors
                page.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
    print('PASS: Update shown only for a release, bottom-right; unsaved-change refusal; offline and no-downgrade hide it')


if __name__ == '__main__':
    if len(sys.argv) > 1:
        main(Path(sys.argv[1]))
    else:
        with tempfile.TemporaryDirectory(prefix='lexeditor-update-browser-') as tmp:
            main(Path(tmp))
