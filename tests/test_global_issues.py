"""Global regressions: real quote data, read-only helper state, credits and bootstrap."""
from __future__ import annotations
import dataclasses
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import runtime_bootstrap as boot
boot.bootstrap_environment()
from desktop_host import HostApi, choose_loading_quote, EXHAUSTED_QUOTE
from plugin_api import GamePlugin, validate_plugin


class Quotes(unittest.TestCase):
    def test_shipped_json_is_valid_and_every_pool_contains_text(self):
        data=json.loads((ROOT/'ui/loading_quotes.json').read_text('utf-8-sig'))
        for key,rows in data.items():
            if key=='shares': continue
            self.assertIsInstance(rows,list,key)
            self.assertTrue(all(isinstance(s,str) and s.strip() for s in rows),key)
        used=set()
        first=lambda rows,**kw:[rows[0]]
        a=choose_loading_quote(data,'ff8',3,first,used)
        b=choose_loading_quote(data,'ff8',3,first,used)
        self.assertNotEqual(a,b)
        self.assertNotIn(a,['Loading editor…',EXHAUSTED_QUOTE])
    def test_missing_and_exhausted_are_different(self):
        self.assertEqual(choose_loading_quote({},'ff8',3,used=set()),'Loading editor…')
        self.assertEqual(choose_loading_quote({'ff8':['A']},'ff8',3,used={'A'}),EXHAUSTED_QUOTE)
    def test_alias_dedup_types_and_finite_rarity(self):
        chooser=Mock(return_value=['A'])
        data={'a':['A',' A ',None,42], 'b':['B'], 'shares':{'a':['b']},'global':['G']}
        choose_loading_quote(data,'a',float('nan'),chooser)
        args,kw=chooser.call_args
        self.assertEqual(args[0],['A','B','G'])
        self.assertEqual(kw['weights'],[1,1,1/3])
    def test_broken_pool_is_not_text_coerced(self):
        self.assertEqual(choose_loading_quote({'ff8':'Wrong shape'},'ff8',3,used=set()),'Loading editor…')


class Helpers(unittest.TestCase):
    def host(self):
        a=GamePlugin('a','A','A','A','#fff',lambda:[],lambda:0,
                     helper_name='Runtime',helper_status=Mock(return_value={'installed':True,'version':'1.1'}),
                     helper_upstream=Mock(return_value={'pinned':'1.0','latest':'1.2','published':'2026-09-01T00:00:00Z','behind':True}),
                     helper_install=Mock(side_effect=AssertionError('Must not install')))
        b=dataclasses.replace(a,plugin_id='b',name='B',helper_upstream=Mock(side_effect=RuntimeError('offline')))
        c=dataclasses.replace(a,plugin_id='c',name='C',helper_upstream=None)
        h=object.__new__(HostApi);h._plugins={'a':a,'b':b,'c':c};h._lock=threading.RLock();h._helper_versions=None
        h._settings=Mock();h._github=Mock();h._github.visible_repository.return_value={'repository':'Lexer-Lux/Lexeditor','login':'Lexer-Lux'}
        h._installations=Mock()
        h._installations.snapshot.side_effect=lambda plugin_id:{'root':'/game','helper':{'installed':True,'version':'1.1','integrity':'ok'}}
        return h
    def test_versions_independent_errors_retained_cache_and_refresh(self):
        h=self.host();result=h.helper_versions();rows=result['helpers']
        self.assertEqual(len(rows),3)
        self.assertEqual((rows[0]['pinned'],rows[0]['installedVersion'],rows[0]['latest']),('1.0','1.1','1.2'))
        self.assertEqual(rows[1]['error'],'offline');self.assertEqual(rows[1]['installedVersion'],'1.1')
        self.assertIn('provider',rows[2]['error'])
        self.assertTrue(h.helper_versions()['cached'])
        h._plugins['a'].helper_upstream.assert_called_once()
        h.helper_versions(True);self.assertEqual(h._plugins['a'].helper_upstream.call_count,2)
        for p in h._plugins.values():p.helper_install.assert_not_called()
    def test_permissions(self):
        h=self.host();h._github.visible_repository.return_value=None
        with self.assertRaises(PermissionError):h.helper_versions()


class Credits(unittest.TestCase):
    def test_all_plugins_have_roles_and_exact_offline_notices(self):
        data=json.loads((ROOT/'ui/credits.json').read_text('utf-8'))
        for path in (ROOT/'games').glob('*/plugin.py'):
            module=importlib.import_module('games.'+path.parent.name+'.plugin')
            p=module.PLUGIN
            self.assertIn(p.plugin_id,data['plugins'])
            rows=data['plugins'][p.plugin_id]
            self.assertTrue(rows['contributions'])
            for credit in rows['contributions']+rows.get('thanks',[]):
                self.assertTrue(credit['name'].strip());self.assertTrue(credit['role'].strip())
            for license in rows.get('licenses',[]):
                self.assertEqual(license['text'],(ROOT/license['sourcePath']).read_text('utf-8-sig'))
    def test_original_ff8_attributions_are_not_dropped(self):
        old=json.loads((ROOT/'games/ff8/credits.json').read_text('utf-8'))
        new=json.loads((ROOT/'ui/credits.json').read_text('utf-8'))['plugins']['ff8']
        for section in ('contributions','thanks'):self.assertEqual(old[section],new[section])
        self.assertEqual([x['name'] for x in old['licenses']],[x['name'] for x in new['licenses']])


class Bootstrap(unittest.TestCase):
    def test_service_whitelist(self):
        with self.assertRaises(ValueError):boot.service_command('os')
        with patch.object(sys,'frozen',True,create=True),patch.object(sys,'executable','/opt/Lexeditor'):
            self.assertEqual(boot.service_command('games.blank.server'),['/opt/Lexeditor','--plugin-service','games.blank.server'])
        self.assertFalse(boot.dispatch_service(['--list']))
        with self.assertRaises(ValueError):boot.dispatch_service(['--plugin-service','os'])
    def test_service_dispatch_runs_only_named_module(self):
        with patch.object(boot.runpy,'run_module') as run,patch.object(sys,'argv',[]):
            self.assertTrue(boot.dispatch_service(['--plugin-service','games.blank.server']))
            run.assert_called_once_with('games.blank.server',run_name='__main__')
    @unittest.skipIf(os.name=='nt','Non-Windows descriptor validation')
    def test_plugins_import_without_registry_and_project_roots_are_absolute(self):
        for path in (ROOT/'games').glob('*/plugin.py'):
            p=importlib.import_module('games.'+path.parent.name+'.plugin').PLUGIN
            # Source fixtures omit large cover art. The production validator is not weakened.
            validate_plugin(dataclasses.replace(p,cover_art=None))
    @unittest.skipIf(os.name=='nt','POSIX path rules')
    def test_relative_xdg_is_ignored(self):
        with patch.dict(os.environ,{'XDG_DATA_HOME':'relative'}),patch.object(sys,'platform','linux'):
            self.assertTrue(boot.user_data_dir().is_absolute())
    def test_real_blank_service_starts_and_stops(self):
        from games.blank.plugin import BlankSession
        session=BlankSession()
        try:self.assertEqual(session.start()['pluginId'],'blank')
        finally:session.stop()
        self.assertTrue(session.wait_closed())

if __name__=='__main__':unittest.main()
