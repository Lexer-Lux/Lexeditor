"""Real bundled bytes in disposable installs; no live game or Steam mutation."""
from pathlib import Path
from contextlib import ExitStack
import hashlib
import json
import os
import shutil
import struct
import tempfile
import unittest
from unittest.mock import patch

from games.warband import wse2_manager as m
from games.warband.game_launch import launch_command, WarbandGameController


class ManagedPackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'game'; self.root.mkdir()
        self.mod = self.root / 'Modules' / 'Selected mod'; self.mod.mkdir(parents=True)
        (self.mod/'module.ini').write_text('module_name = Chosen')
        (self.root/'mb_warband.exe').write_bytes(b'original stock game')
        (self.root/'steam_api.dll').write_bytes(b'original stock Steam DLL')
        self.manifest = m._manifest()

    def install(self, **kwargs):
        return m.install(self.root, closed_check=lambda root: None, **kwargs)

    def test_shipped_archive_is_exact_and_contains_steam_but_no_updater(self):
        manifest, files = m.package_files()
        self.assertEqual(len(files), 58)
        self.assertEqual(files['steam_appid.txt'], b'48700')
        self.assertNotIn('wse2_launcher.exe', files)
        self.assertNotIn('steam_api.dll', files)
        for name, machine in [('mb_warband_wse2.exe', 0x14c), ('mb_warband_wse2_x64.exe', 0x8664),
                              ('steam_api_wse2.dll',0x14c), ('steam_api64.dll',0x8664)]:
            raw=files[name];offset=struct.unpack_from('<I',raw,0x3c)[0]
            self.assertEqual(raw[offset:offset+4],b'PE\0\0')
            self.assertEqual(struct.unpack_from('<H',raw,offset+4)[0],machine)
        self.assertIn(b'Steam API initialized.',files['mb_warband_wse2.exe'])
        self.assertIn(b'Initializing Steam achievement manager...',files['mb_warband_wse2.exe'])

    def test_install_is_offline_pinned_and_idempotent(self):
        with patch('urllib.request.urlopen', side_effect=AssertionError('network during install')):
            self.assertTrue(self.install()['installed'])
            self.assertFalse(self.install()['changed'])
        self.assertEqual((self.root/'mb_warband.exe').read_bytes(), b'original stock game')
        self.assertEqual((self.root/'steam_api.dll').read_bytes(), b'original stock Steam DLL')
        status=m.status(self.root)
        self.assertTrue(status['managed']); self.assertFalse(status['steamVerified'])
        self.assertEqual(status['version'],m.PINNED_RELEASE)
        self.assertFalse((self.root/'wse2_launcher.exe').exists())

    def test_replaces_wrong_version_with_backups_and_preserves_unmanaged_files(self):
        (self.root/'mb_warband_wse2.exe').write_bytes(b'old wse2')
        (self.root/'wse2_launcher.exe').write_bytes(b'existing launcher is not ours')
        (self.root/'postFX.fx').write_bytes(b'original shader')
        self.install()
        receipt=m._json_read(self.root/'.lexeditor/wse2/receipt.json')
        backup=self.root/'.lexeditor/wse2/backups'/receipt['backup']/'files'
        self.assertEqual((backup/'mb_warband_wse2.exe').read_bytes(),b'old wse2')
        self.assertEqual((backup/'postFX.fx').read_bytes(),b'original shader')
        self.assertEqual((self.root/'wse2_launcher.exe').read_bytes(),b'existing launcher is not ours')

    def test_arbitrary_wse2_is_not_accepted_or_run(self):
        (self.root/'mb_warband_wse2.exe').write_bytes(b'unknown')
        called=[]
        controller=WarbandGameController(lambda *args:called.append(args))
        with self.assertRaisesRegex(RuntimeError,'pinned'):controller.launch(self.root,self.mod)
        self.assertEqual(called,[])

    def test_real_package_passes_launch_preflight_with_selected_mod(self):
        self.install()
        self.assertEqual(launch_command(self.root,self.mod)[1:],['--module','Selected mod','--no-intro'])

    def test_drift_even_with_preserved_mtime_is_rejected(self):
        self.install(); exe=self.root/'mb_warband_wse2.exe';old=exe.stat()
        raw=bytearray(exe.read_bytes());raw[-1]^=1;exe.write_bytes(raw)
        os.utime(exe,ns=(old.st_atime_ns,old.st_mtime_ns))
        self.assertFalse(m.status(self.root)['installed'])
        with self.assertRaisesRegex(RuntimeError,'pinned'):launch_command(self.root,self.mod)
        self.assertTrue(self.install()['installed'])

    def test_steam_appid_drift_is_rejected(self):
        self.install();(self.root/'steam_appid.txt').write_text('480')
        with self.assertRaisesRegex(RuntimeError,'pinned'):launch_command(self.root,self.mod)

    def test_receipt_cannot_bless_another_install(self):
        self.install();second=self.root.parent/'second';shutil.copytree(self.root,second)
        self.assertFalse(m.status(second)['installed'])
        self.assertEqual(m.status(second)['integrity'],'unmanaged')

    def test_status_and_upstream_never_write_install_files(self):
        before=list(self.root.rglob('*'))
        self.assertFalse(m.status(self.root)['installed'])
        result=m.upstream_release(lambda url:{'tag_name':'v1.1.6.0','published_at':'2026-09-06T00:00:00Z'})
        self.assertTrue(result['behind']);self.assertEqual(result['pinned'],m.PINNED_RELEASE)
        self.assertEqual(list(self.root.rglob('*')),before)

    def test_upstream_failure_keeps_pin_and_older_release_is_not_newer(self):
        def fail(url):raise OSError('offline')
        self.assertEqual(m.upstream_release(fail)['pinned'],m.PINNED_RELEASE)
        self.assertFalse(m.upstream_release(lambda url:{'tag_name':'v1.1.4.7'})['behind'])

    def test_corrupt_bundle_touches_no_game_files(self):
        bundle=self.root.parent/'bundle';shutil.copytree(m.PACKAGE_ROOT,bundle)
        (bundle/self.manifest['archive']).write_bytes(b'bad')
        with self.assertRaisesRegex(RuntimeError,'SHA-256'):self.install(package_root=bundle)
        self.assertFalse((self.root/'.lexeditor').exists())

    def test_running_game_blocks_before_backups_or_writes(self):
        def busy(root):raise RuntimeError('Close Warband')
        with self.assertRaisesRegex(RuntimeError,'Close Warband'):
            m.install(self.root,closed_check=busy)
        self.assertFalse((self.root/'mb_warband_wse2.exe').exists())
        self.assertFalse((self.root/'.lexeditor/wse2/backups').exists())

    def test_linked_resource_directory_is_rejected(self):
        elsewhere=self.root.parent/'elsewhere';elsewhere.mkdir()
        try:(self.root/'CommonRes').symlink_to(elsewhere,target_is_directory=True)
        except OSError:self.skipTest('symlink privileges unavailable')
        with self.assertRaisesRegex(RuntimeError,'linked'):self.install()
        self.assertEqual(list(elsewhere.iterdir()),[])

    def test_failed_install_restores_old_bytes_and_removes_new_ones(self):
        (self.root/'postFX.fx').write_bytes(b'old shader')
        original=m._atomic;hit=[]
        def fail(path,data):
            if path==self.root/'postFX_WSE2.fx' and not hit:
                hit.append(True);raise OSError('simulated disk failure')
            return original(path,data)
        with patch.object(m,'_atomic',side_effect=fail):
            with self.assertRaisesRegex(RuntimeError,'previous files restored'):self.install()
        self.assertEqual((self.root/'postFX.fx').read_bytes(),b'old shader')
        self.assertFalse((self.root/'mb_warband_wse2.exe').exists())
        self.assertFalse((self.root/'.lexeditor/wse2/pending.json').exists())

    def test_interrupted_install_recovers_on_explicit_retry(self):
        original=m._atomic
        def interrupt(path,data):
            if path==self.root/'postFX_WSE2.fx':raise KeyboardInterrupt('crash fixture')
            return original(path,data)
        with patch.object(m,'_atomic',side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):self.install()
        self.assertTrue(m.status(self.root)['pending'])
        self.assertFalse(m.status(self.root)['installed'])
        self.assertTrue(self.install()['installed'])

    def test_external_edit_during_failed_install_is_not_overwritten(self):
        original=m._atomic
        def interrupt(path,data):
            if path==self.root/'postFX_WSE2.fx':raise KeyboardInterrupt('crash fixture')
            return original(path,data)
        with patch.object(m,'_atomic',side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):self.install()
        (self.root/'postFX.fx').write_bytes(b'user edit after crash')
        with self.assertRaisesRegex(RuntimeError,'external edit'):self.install()
        self.assertEqual((self.root/'postFX.fx').read_bytes(),b'user edit after crash')
        self.assertTrue((self.root/'.lexeditor/wse2/pending.json').exists())

    def test_forged_recovery_paths_are_rejected(self):
        folder=self.root/'.lexeditor/wse2';folder.mkdir(parents=True)
        m._json_write(folder/'pending.json',{'id':'a'*32,'root':m._root_identity(self.root),'files':[{'path':'../escape','original':None}]})
        with self.assertRaisesRegex(RuntimeError,'recovery file list'):self.install()

    def test_no_game_reports_absent_without_creating_default_paths(self):
        self.assertFalse(m.status(None)['installed'])
        with self.assertRaisesRegex(RuntimeError,'complete Warband'):m.install(self.root.parent/'absent')


@unittest.skipUnless(os.name == 'nt', 'Windows process inspection')
class ProcessGuardTests(unittest.TestCase):
    def test_current_live_process_prevents_install(self):
        import sys
        with patch.object(m, 'PROCESS_NAMES', (Path(sys.executable).name.casefold(),)):
            with self.assertRaisesRegex(RuntimeError, 'Close Warband'):
                m._assert_closed(Path.cwd())

    def test_absent_process_name_does_not_prevent_install(self):
        with patch.object(m, 'PROCESS_NAMES', ('no-such-lexeditor-fixture.exe',)):
            m._assert_closed(Path.cwd())

if __name__=='__main__':unittest.main()
