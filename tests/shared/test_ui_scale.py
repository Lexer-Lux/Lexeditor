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
