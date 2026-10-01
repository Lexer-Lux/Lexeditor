"""Scale persistence and native zoom policy without opening a window."""
import sys
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from core.settings_manager import SettingsStore
from core.desktop_host import HostApi
from core.windows_host import set_ui_scale
import pytest
from test_shared_ui_feedback import framework, page


@pytest.mark.parametrize('chooser',[False,True])
def test_menu_and_pager_follow_native_zoom(page,tmp_path,chooser):
    framework(page)
    page.evaluate('''chooser=>{
      const U=LexeditorUI;
      window.pywebview={api:{ui_scale:async percent=>({percent:percent??100})}};
      const header=U.el('div',{class:'lex-shell-command-row',
        style:chooser?'--lex-command-row-height:var(--lex-chooser-menu-height,9vh)':''},
        U.el('strong',{},chooser?'Games':'Editor'),U.uiScaleControl());
      document.body.replaceChildren(header,U.el('main',{},'Content'),U.pager({page:0,pages:2,pageSize:10,total:20}));
    }''',chooser)
    slider=page.get_by_role('slider',name='UI scale',exact=True)
    for percent in [50,100,150]:
        scale=percent/100
        # Native page zoom reduces the CSS viewport while multiplying CSS
        # pixels on screen. Test those two effects separately without a window.
        page.set_viewport_size({'width':round(1200/scale),'height':round(900/scale)})
        slider.evaluate('(n,p)=>{n.value=p;n.dispatchEvent(new Event("input",{bubbles:true}));n.dispatchEvent(new Event("change",{bubbles:true}))}',percent)
        page.wait_for_function('(s)=>document.documentElement.style.getPropertyValue("--lex-ui-scale")===String(s)',arg=scale)
        menu=page.locator('.lex-shell-command-row').bounding_box()['height']
        pager=page.locator('.lex-pager').bounding_box()['height']
        assert menu*scale==pytest.approx(81*scale,abs=1)
        assert pager*scale==pytest.approx(54*scale,abs=1)
    page.screenshot(path=str(tmp_path/f'zoom-bars-{chooser}.png'))
    page.locator('.lex-ui-scale').click(button='right')
    page.wait_for_function('document.documentElement.style.getPropertyValue("--lex-ui-scale")==="1"')

class ScaleTests(unittest.TestCase):
    def test_saved_range_and_native_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=SettingsStore(path=Path(tmp)/"settings.json")
            api=HostApi.__new__(HostApi)
            api._settings=store
            api._bound_window=lambda: "window"
            with patch("core.desktop_host.set_ui_scale") as apply:
                for percent in (50,100,150):
                    self.assertEqual(api.ui_scale(percent),{"percent":percent})
                    apply.assert_called_with("window",percent)
                    self.assertEqual(api.ui_scale(),{"percent":percent})
                for percent in (49,151):
                    with self.assertRaises(ValueError):api.ui_scale(percent)
            self.assertEqual(SettingsStore(path=store.path).snapshot()["viewPreferences"]["ui-scale"],150)
        settings=SimpleNamespace(IsZoomControlEnabled=True,IsPinchZoomEnabled=True)
        view=SimpleNamespace(CoreWebView2=SimpleNamespace(Settings=settings),ZoomFactor=1)
        native=SimpleNamespace(webview=view)
        with patch("core.windows_host._invoke",side_effect=lambda _,fn:fn()):
            set_ui_scale(SimpleNamespace(native=native),125)
        self.assertEqual(view.ZoomFactor,1.25)
        self.assertFalse(settings.IsZoomControlEnabled)
        self.assertFalse(settings.IsPinchZoomEnabled)

if __name__=="__main__":unittest.main()
