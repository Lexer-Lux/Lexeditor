"""Root-aware helper registration and read-only Home checker contracts."""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from dataclasses import replace
from types import SimpleNamespace, ModuleType
import unittest
import webbrowser
from unittest.mock import Mock, patch

# Windows registry discovery is outside these isolated API tests. Windows CI
# imports the real module; Linux supplies only the unavailable import boundary.
if os.name != 'nt':
    with patch.dict(sys.modules, {'winreg': ModuleType('winreg')}):
        from desktop_host import HostApi
        from game_installation import GameInstallationManager
else:
    from desktop_host import HostApi
    from game_installation import GameInstallationManager
from games.warband.plugin import PLUGIN
from games.warband import wse2_manager as wse2


class HelperPanelTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.game=self.root/'selected-game';self.game.mkdir();(self.game/'Modules').mkdir();(self.game/'mb_warband.exe').write_bytes(b'STOCK')
        self.upstream=Mock(return_value={'pinned':wse2.PINNED_RELEASE,'latest':'v1.1.6.0',
            'published':'2026-09-06T00:00:00Z','source':wse2.REPOSITORY,'behind':True})
        self.plugin=replace(PLUGIN,helper_upstream=self.upstream,
            helper_install_for_root=lambda root:wse2.install(root,closed_check=lambda root:None))
        self.manager=GameInstallationManager({'warband':self.plugin},config_path=self.root/'locations.json',auto_scan=False)
        self.manager._states['warband']=self.manager._state('added','Ready',root=str(self.game))
        self.api=HostApi.__new__(HostApi);self.api._plugins={'warband':self.plugin}
        self.api._settings=SimpleNamespace(snapshot=lambda:{'updateCheckFrequency':'never'})
        self.api._github=Mock();self.api._github.visible_repository.return_value={'repository':'Lexer-Lux/Lexeditor','login':'Lexer-Lux'}
        self.api._installations=self.manager;self.api._lock=threading.RLock();self.api._helper_versions=None

    def test_plugin_registers_pin_and_all_root_aware_hooks(self):
        self.assertEqual(PLUGIN.helper_name,'WSE2')
        self.assertIs(PLUGIN.helper_install_for_root,wse2.install)
        self.assertIs(PLUGIN.helper_status_for_root,wse2.status)
        self.assertIs(PLUGIN.helper_upstream,wse2.upstream_release)

    def test_install_uses_selected_root_not_imported_default(self):
        before=self.manager.snapshot('warband');self.assertFalse(before['canOpen'])
        self.assertEqual(before['helper']['pinned'],wse2.PINNED_RELEASE)
        result=self.api.install_helper('warband')
        self.assertTrue(result['installed']);self.assertTrue(result['canOpen'])
        self.assertTrue((self.game/'mb_warband_wse2.exe').exists())

    def test_upstream_cache_and_refresh_keep_installed_state_fresh(self):
        first=self.api.helper_versions();self.assertFalse(first['cached'])
        self.assertEqual(first['helpers'][0]['installedVersion'],'')
        self.api.install_helper('warband')
        second=self.api.helper_versions();self.assertTrue(second['cached'])
        self.assertEqual(second['helpers'][0]['installedVersion'],wse2.PINNED_RELEASE)
        self.assertEqual(self.upstream.call_count,1)
        third=self.api.helper_versions(True);self.assertFalse(third['cached'])
        self.assertEqual(self.upstream.call_count,2)
        self.assertTrue(third['helpers'][0]['releaseNotes'].endswith('/releases/tag/v1.1.6.0'))

    def test_upstream_failure_preserves_pin_and_actual_install(self):
        self.api.install_helper('warband');self.upstream.side_effect=OSError('GitHub offline')
        row=self.api.helper_versions()['helpers'][0]
        self.assertEqual(row['pinned'],wse2.PINNED_RELEASE)
        self.assertEqual(row['installedVersion'],wse2.PINNED_RELEASE)
        self.assertIn('offline',row['error'])

    def test_absent_game_is_listed_and_does_not_read_default_install(self):
        self.manager._states['warband']=self.manager._state('not-added','Absent',root=None)
        with patch.object(wse2,'status',side_effect=AssertionError('default install read')):
            row=self.api.helper_versions()['helpers'][0]
        self.assertEqual(row['pinned'],wse2.PINNED_RELEASE)
        self.assertEqual(row['installedVersion'],'')
        with self.assertRaisesRegex(RuntimeError,'Locate'):self.api.install_helper('warband')

    def test_developer_permission_and_read_only_checker(self):
        self.api._plugins['warband']=replace(self.plugin,helper_install_for_root=Mock(side_effect=AssertionError('installed during check')))
        self.api.helper_versions();self.api.helper_versions(True)
        self.assertFalse((self.game/'.lexeditor').exists())
        self.api._github.visible_repository.return_value=None
        with self.assertRaises(PermissionError):self.api.helper_versions()
        with self.assertRaises(PermissionError):self.api.open_helper_release_notes('warband')

    def test_release_notes_are_external_and_use_cached_approved_url(self):
        self.api.helper_versions()
        with patch.object(webbrowser,'open',return_value=True) as open_url:
            self.assertTrue(self.api.open_helper_release_notes('warband')['opened'])
            self.assertIn('/releases/tag/v1.1.6.0',open_url.call_args.args[0])
        self.api._helper_versions[0]['releaseNotes']='https://github.com.evil.test/example'
        with self.assertRaises(ValueError):self.api.open_helper_release_notes('warband')

    def test_failure_of_one_helper_does_not_hide_other_rows(self):
        other=replace(self.plugin,plugin_id='test-helper',name='Other',helper_upstream=Mock(side_effect=ValueError('failure')))
        self.api._plugins['test-helper']=other
        self.manager._plugins['test-helper']=other
        self.manager._states['test-helper']=self.manager._state('not-added','Absent',root=None)
        rows=self.api.helper_versions()['helpers'];self.assertEqual(len(rows),2)
        self.assertTrue(next(row for row in rows if row['pluginId']=='warband')['latest'])
        self.assertIn('error',next(row for row in rows if row['pluginId']=='test-helper'))

if __name__=='__main__':unittest.main()
