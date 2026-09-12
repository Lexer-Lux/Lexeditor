import importlib.util
from pathlib import Path
import unittest
import json
import xml.etree.ElementTree as ET

spec=importlib.util.spec_from_file_location('duration_catalog',Path(__file__).resolve().parents[1]/'tools/probes/rdr2_duration/catalog.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class DurationProbe(unittest.TestCase):
 def fixture(self):
  return '<ItemDatabaseParser><!--keep--><effectsids><item><key>BASE_H</key><id>EFFECT_HEALTH_OVERPOWERED</id></item><item><key>BASE_S</key><id>EFFECT_STAMINA_OVERPOWERED</id></item></effectsids><catalog><items>'+''.join(f'<item key="{key}"><key>{key}</key><ui><key>{key}</key></ui><effectids><item><key>BASE_H</key></item></effectids><unknown value="keep"/></item>' for key in m.ITEMS)+'<item key="UNRELATED"><key>UNRELATED</key></item></items></catalog></ItemDatabaseParser>'
 def test_only_effect_links_and_eight_definitions_change(self):
  original=self.fixture().replace('<effectids><item><key>BASE_H</key></item></effectids>','<effectids />',1);out=m.prepare(original);r=ET.fromstring(out)
  self.assertEqual(len(r.findall('./effectsids/item')),10)
  for i,case in enumerate(m.CASES):
   a,b=m.item_span(original,case['item']);c,d=m.item_span(out,case['item'])
   import re
   strip=lambda text:re.sub(r'<effectids\s*/>|<effectids>.*?</effectids>','',text)
   self.assertEqual(strip(original[a:b]),strip(out[c:d]))
   effect=r.findall('./effectsids/item')[i+2]
   self.assertEqual(effect.findtext('durationcategory'),f'EFFECT_DURATION_CATEGORY_{case["category"]}')
   self.assertEqual(effect.find('time').get('value'),str(case['time']))
  self.assertIn('<!--keep-->',out);self.assertIn('<item key="UNRELATED"><key>UNRELATED</key></item>',out)
 def test_repeated_prepare_and_missing_item_fail(self):
  with self.assertRaises(ValueError):m.prepare(m.prepare(self.fixture()))
  with self.assertRaises(ValueError):m.prepare(self.fixture().replace(m.ITEMS[0],'MISSING'))
 def test_catalog_install_restore_and_changed_source_guard(self):
  import tempfile,sys
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);catalog=root/'catalog';bundle=root/'bundle';original=self.fixture().encode();catalog.write_bytes(original)
   def run(action):
    with patch.object(sys,'argv',['catalog.py',action,'--catalog',str(catalog),'--bundle',str(bundle)]):m.main()
   run('prepare');run('install');candidate=catalog.read_bytes()
   catalog.write_bytes(candidate+b' ')
   with self.assertRaises(ValueError):run('restore')
   catalog.write_bytes(candidate);run('restore');self.assertEqual(catalog.read_bytes(),original)
   with self.assertRaises(ValueError):run('prepare')
 def test_probe_and_mod_restore_preserve_exact_bytes(self):
  import tempfile
  spec=importlib.util.spec_from_file_location('duration_deploy',Path(__file__).resolve().parents[1]/'tools/probes/rdr2_duration/deploy.py');d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);game=root/'game';bundle=root/'bundle';game.mkdir();bundle.mkdir()
   (game/'GameplayTweaks.asi').write_bytes(b'original gameplay');(game/'vfs.asi').write_bytes(b'loader')
   d.isolate('isolate',game,bundle)
   self.assertFalse((game/'GameplayTweaks.asi').exists());self.assertEqual((game/'vfs.asi').read_bytes(),b'loader')
   with self.assertRaises(ValueError):d.isolate('isolate',game,bundle)
   d.isolate('restore-mods',game,bundle);self.assertEqual((game/'GameplayTweaks.asi').read_bytes(),b'original gameplay')
   asi=root/'candidate.asi';asi.write_bytes(b'probe');d.change('install',game,bundle,asi)
   (game/'DurationProbe.asi').write_bytes(b'newer')
   with self.assertRaises(ValueError):d.change('restore',game,bundle)
   (game/'DurationProbe.asi').write_bytes(b'probe');d.change('restore',game,bundle)
   self.assertFalse((game/'DurationProbe.asi').exists())
 def test_activation_failures_roll_back_and_repeats_are_bounded(self):
  import tempfile,sys,importlib
  from unittest.mock import patch
  sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/probes/rdr2_duration'))
  c=importlib.import_module('coordinator')
  for stage in ('isolate','catalog','probe','marker',None):
   with self.subTest(stage=stage),tempfile.TemporaryDirectory() as temp:
    root=Path(temp);game=root/'game';game.mkdir();bundle=root/'bundle';target=game/'catalog';target.write_text(self.fixture());asi=root/'candidate.asi';asi.write_bytes(b'probe')
    (game/'GameplayTweaks.asi').write_bytes(b'original mod');(game/'vfs.asi').write_bytes(b'loader')
    with patch.object(sys,'argv',['catalog.py','prepare','--catalog',str(target),'--bundle',str(bundle)]):c.catalog.main()
    info=json.loads((bundle/'manifest.json').read_text());info['probe_sha256']=c.deploy.digest(asi.read_bytes());(bundle/'manifest.json').write_text(json.dumps(info))
    original=target.read_bytes();isolate=c.deploy.isolate;change=c.deploy.change;cat=c.catalog_action;write=Path.write_text
    def iso(action,*args):
     result=isolate(action,*args)
     if stage=='isolate' and action=='isolate':raise OSError('isolation failure')
     return result
    def catalog_call(action,*args):
     result=cat(action,*args)
     if stage=='catalog' and action=='install':raise OSError('catalog failure')
     return result
    def probe(action,*args):
     result=change(action,*args)
     if stage=='probe' and action=='install':raise OSError('probe failure')
     return result
    def marker(path,*args,**kwargs):
     if stage=='marker' and path.name=='active.json':raise OSError('marker failure')
     return write(path,*args,**kwargs)
    with patch.object(c.deploy,'isolate',iso),patch.object(c.deploy,'change',probe),patch.object(c,'catalog_action',catalog_call),patch.object(Path,'write_text',marker):
     if stage:
      with self.assertRaisesRegex(RuntimeError,'Original files were restored'):c.activate(game,bundle,asi)
     else:
      c.activate(game,bundle,asi)
      with self.assertRaisesRegex(RuntimeError,'already active'):c.activate(game,bundle,asi)
      c.restore(game,bundle)
    c.restore(game,bundle);c.restore(game,bundle)
    self.assertEqual(target.read_bytes(),original);self.assertEqual((game/'GameplayTweaks.asi').read_bytes(),b'original mod')
    self.assertFalse((game/'DurationProbe.asi').exists());self.assertFalse((bundle/'disabled-asi').exists())
 def test_changed_prepared_probe_has_zero_live_writes(self):
  import tempfile,sys,importlib
  from unittest.mock import patch
  sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/probes/rdr2_duration'));c=importlib.import_module('coordinator')
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);game=root/'game';game.mkdir();bundle=root/'bundle';target=game/'catalog';target.write_text(self.fixture());asi=root/'candidate.asi';asi.write_bytes(b'probe');(game/'GameplayTweaks.asi').write_bytes(b'mod')
   with patch.object(sys,'argv',['catalog.py','prepare','--catalog',str(target),'--bundle',str(bundle)]):c.catalog.main()
   info=json.loads((bundle/'manifest.json').read_text());info['probe_sha256']=c.deploy.digest(asi.read_bytes());(bundle/'manifest.json').write_text(json.dumps(info))
   before={p.name:p.read_bytes() for p in game.iterdir()};asi.write_bytes(b'unreviewed')
   with patch.object(c.deploy,'isolate',side_effect=AssertionError('isolation must not run')):
    with self.assertRaisesRegex(ValueError,'Prepared probe changed'):c.activate(game,bundle,asi)
   self.assertEqual({p.name:p.read_bytes() for p in game.iterdir()},before)
   self.assertFalse((bundle/'isolation.json').exists())
 def test_incomplete_probe_stage_never_becomes_live(self):
  import tempfile,sys,importlib
  from unittest.mock import patch
  sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/probes/rdr2_duration'));d=importlib.import_module('deploy')
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);game=root/'game';game.mkdir();bundle=root/'bundle';bundle.mkdir();asi=root/'candidate.asi';asi.write_bytes(b'probe');original=Path.open
   class ShortWriter:
    def __enter__(self):self.handle=original(game/'DurationProbe.asi.staging','xb');return self
    def write(self,data):self.handle.write(data[:2]);return 2
    def __exit__(self,*args):self.handle.close()
   def opening(path,*args,**kwargs):return ShortWriter() if path.name=='DurationProbe.asi.staging' and args==('xb',) else original(path,*args,**kwargs)
   with patch.object(Path,'open',opening):
    with self.assertRaises(RuntimeError):d.change('install',game,bundle,asi)
   self.assertEqual(list(game.iterdir()),[]);self.assertFalse((bundle/'probe-install.json').exists())
 def test_failed_rollback_retains_exact_recovery(self):
  import tempfile,sys,importlib
  from unittest.mock import patch
  sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/probes/rdr2_duration'));c=importlib.import_module('coordinator')
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);game=root/'game';game.mkdir();bundle=root/'bundle';target=game/'catalog';target.write_text(self.fixture());asi=root/'candidate.asi';asi.write_bytes(b'probe');(game/'GameplayTweaks.asi').write_bytes(b'mod')
   with patch.object(sys,'argv',['catalog.py','prepare','--catalog',str(target),'--bundle',str(bundle)]):c.catalog.main()
   info=json.loads((bundle/'manifest.json').read_text());info['probe_sha256']=c.deploy.digest(asi.read_bytes());(bundle/'manifest.json').write_text(json.dumps(info))
   change=c.deploy.change
   def fail(action,*args):
    if action=='install':change(action,*args);raise OSError('after install')
    raise OSError('restore denied')
   with patch.object(c.deploy,'change',fail):
    with self.assertRaisesRegex(RuntimeError,'Recovery incomplete'):c.activate(game,bundle,asi)
   self.assertTrue((bundle/'probe-install.json').exists());self.assertEqual((game/'DurationProbe.asi').read_bytes(),b'probe')
   self.assertEqual((game/'GameplayTweaks.asi').read_bytes(),b'mod')
   with self.assertRaisesRegex(RuntimeError,'recovery pending'):c.activate(game,bundle,asi)
   c.restore(game,bundle);self.assertFalse((game/'DurationProbe.asi').exists())
if __name__=='__main__':unittest.main()
