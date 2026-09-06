"""Warband regressions using temporary fixtures, never an installed game/mod."""
from __future__ import annotations
import ctypes
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image
from games.warband import server, model_preview as models, item_icons as icons
from games.warband import game_font
from games.warband.game_launch import launch_command, WarbandGameController, WindowsGameJob


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); (self.root/'ModuleSystem').mkdir();(self.root/'Module').mkdir()
        (self.root/'Module'/'module.ini').write_text('module_name = Fixture')
        (self.root/'settings.ini').write_text('[Test]\nvalue=1\n')
        for name in ('module_troops.py','module_items.py','module_skills.py'):
            (self.root/'ModuleSystem'/name).write_text('')
        for key,value in {'PROJECT':self.root,'MODULE_SYSTEM':self.root/'ModuleSystem','SETTINGS':self.root/'settings.ini'}.items():
            p=patch.object(server,key,value);p.start();self.addCleanup(p.stop)

    def test_only_structured_settings_count_integrated(self):
        rows={r['filename']:r for r in server.data_map_rows()['rows']}
        self.assertEqual(rows['settings.ini']['coverage'],'structured')
        self.assertEqual(rows['module_skills.py']['coverage'],'source')
        self.assertEqual(rows['module_items.py']['coverage'],'view')
        self.assertEqual(rows['module_troops.py']['view'],'troops')
        self.assertEqual(server.data_map_rows()['counts']['integrated'],1)
        self.assertTrue(rows['module_skills.py']['openable'])
        self.assertFalse(rows['module_quests.py']['openable'])
        self.assertEqual(rows['module_quests.py']['coverage'],'unavailable')

    def test_installed_module_ini_resolves_without_source(self):
        (self.root/'module.ini').write_text('module_name = Installed')
        self.assertEqual(server.resolve_catalog_file('module.ini'),self.root/'module.ini')

    def test_no_source_is_empty_not_boot_error(self):
        with patch.object(server,'MODULE_SYSTEM',self.root/'missing'),patch.object(server,'SETTINGS',self.root/'missing.ini'):
            self.assertEqual(server.item_rows(),[])
            self.assertEqual(server.upgrade_rows(),[])
            self.assertEqual(server.settings_rows(),[])
            self.assertFalse(next(r for r in server.data_map_rows()['rows'] if r['filename']=='settings.ini')['openable'])

    def test_source_path_traversal_is_rejected(self):
        self.assertIsNone(server.resolve_catalog_file('../settings.ini'))

    def test_source_edit_roundtrip_preserves_backup(self):
        path=self.root/'ModuleSystem'/'module_skills.py'
        path.write_text('old = 1\n')
        with patch.object(server,'resolve_catalog_file',return_value=path):
            result=server.save_catalog_file('module_skills.py','old = 2\n','utf-8')
        self.assertEqual(path.read_text(),'old = 2\n')
        self.assertEqual(Path(result['backup']).read_text(),'old = 1\n')


class FontTests(unittest.TestCase):
    def test_installed_metrics_and_exact_dds_alpha(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);dds=root/'font.dds';xml=root/'font_data.xml';png=root/'generated.png'
            source=Image.new('RGBA',(4,4),(0,0,0,0));source.putpixel((1,1),(150,80,20,117));source.save(dds,'DDS')
            xml.write_text('<Font width="4" height="4" font_size="4" line_spacing="6"><FontDetails><character code="65" u="1" v="1" w="2" h="2" preshift="0" yadjust="3" postshift="2"/></FontDetails></Font>')
            with patch.object(game_font,'FONT_TEXTURE',dds),patch.object(game_font,'FONT_DATA',xml),patch.object(game_font,'ATLAS_PNG',png):
                manifest=game_font.manifest();self.assertTrue(manifest['available']);self.assertEqual(manifest['characters']['65']['postshift'],2)
                actual=game_font.atlas_path()
                with Image.open(actual) as converted,Image.open(dds) as original:
                    self.assertEqual(converted.getchannel('A').tobytes(),original.convert('RGBA').getchannel('A').tobytes())


class DependencyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.mesh=self.root/'mesh.brf';self.material=self.root/'material.brf';self.texture=self.root/'diffuse.dds';self.tool=self.root/'reader.exe'
        for file in (self.mesh,self.material,self.tool):file.write_bytes(b'fixture')
        Image.new('RGBA',(4,4),(200,140,50,255)).save(self.texture,format='DDS')
        values={'CACHE_ROOT':self.root/'cache','MODULE_ROOT':self.root/'module','BRF_SYNC':self.tool,'MODULE_TEXTURES':self.root,'GAME_TEXTURES':self.root/'game-textures'}
        for key,value in values.items():
            p=patch.object(models,key,value);p.start();self.addCleanup(p.stop)
        self.records={'meshes':(self.mesh,{'name':'sword','material':'steel'}),'materials':(self.material,{'name':'steel','diffuseA':'diffuse'})}
        p=patch.object(models,'_find_record',side_effect=lambda kind,name:self.records.get(kind));p.start();self.addCleanup(p.stop)

    def key(self):return models.dependencies('sword')['key']
    def test_mesh_name_validation(self):
        for mesh in ('','../escape','a/b','x\\y'):
            with self.assertRaises(models.PreviewUnavailable):models.dependencies(mesh)
    def test_missing_mesh(self):
        self.records.pop('meshes')
        with self.assertRaisesRegex(models.PreviewUnavailable,'does not load'):self.key()
    def test_missing_material_fails_not_gray_preview(self):
        self.records.pop('materials')
        with self.assertRaisesRegex(models.PreviewUnavailable,'missing material'):self.key()
    def test_missing_diffuse_fails(self):
        self.texture.unlink()
        with self.assertRaisesRegex(models.PreviewUnavailable,'diffuse texture'):self.key()
    def test_material_resource_mutation_invalidates(self):
        before=self.key();self.material.write_bytes(b'changed material record');self.assertNotEqual(before,self.key())
    def test_mesh_mutation_invalidates(self):
        before=self.key();self.mesh.write_bytes(b'changed mesh');self.assertNotEqual(before,self.key())
    def test_texture_mutation_invalidates_even_with_preserved_mtime(self):
        before=self.key();stat=self.texture.stat();self.texture.write_bytes(self.texture.read_bytes()+b'changed')
        os.utime(self.texture,ns=(stat.st_atime_ns,stat.st_mtime_ns));self.assertNotEqual(before,self.key())
    def test_module_identity_isolated(self):
        before=self.key()
        with patch.object(models,'MODULE_ROOT',self.root/'another-module'):self.assertNotEqual(before,self.key())
    def test_texture_path_traversal(self):
        self.assertIsNone(models._texture_file('../diffuse'))
        self.assertIsNone(models.texture_path('../outside'))
    def test_obj_geometry_and_preview_cache(self):
        obj=self.root/'mesh.obj';obj.write_text('v -1 0 -1\nv 1 0 -1\nv 0 0 1\nvt 0 0\nvt 1 0\nvt .5 1\nvn 0 -1 0\nf 1/1/1 2/2/1 3/3/1\n')
        with patch.object(models,'_export_mesh',return_value=obj) as exporter:
            first=models.preview('sword');second=models.preview('sword')
            self.assertEqual(first,second);self.assertEqual(exporter.call_count,1)
            self.assertEqual(first['summary']['triangles'],1)
            self.assertTrue(models.texture_path(first['cacheKey']).is_file())


def triangle_data(key='a'*64):
    return {'cacheKey':key,'geometry':{'positions':[[-1,0,-1],[1,0,-1],[0,0,1]],
        'normals':[[0,-1,0]]*3,'texCoords':[[0,0],[1,0],[.5,1]],'triangles':[[0,1,2]],
        'bounds':{'min':[-1,0,-1],'max':[1,0,1]}}}


class IconTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.texture=self.root/'texture.png';Image.new('RGBA',(8,8),(180,80,30,255)).save(self.texture)
    def test_render_is_png_fitted_and_repeatable(self):
        first=self.root/'first.png';second=self.root/'second.png'
        icons.render_icon(triangle_data(),self.texture,first);icons.render_icon(triangle_data(),self.texture,second)
        self.assertEqual(first.read_bytes(),second.read_bytes())
        with Image.open(first) as image:
            self.assertEqual(image.size,(192,192));self.assertEqual(image.format,'PNG')
            self.assertGreater(len(set(image.get_flattened_data() if hasattr(image,"get_flattened_data") else image.getdata())),2)
            self.assertEqual(image.getpixel((0,0)),(222,216,203,255))
    def test_renderer_revision_part_of_identity(self):
        before=icons.icon_key('a'*64)
        with patch.object(icons,'RENDER_VERSION','changed'):self.assertNotEqual(before,icons.icon_key('a'*64))
    def test_background_deduplicates_and_reuses_png(self):
        cache=icons.IconCache()
        with patch.object(models,'CACHE_ROOT',self.root/'cache'),patch.object(models,'dependencies',return_value={'key':'a'*64}),patch.object(models,'preview',return_value=triangle_data()) as preview,patch.object(models,'texture_path',return_value=self.texture):
            self.assertIsNone(cache.request('sword'));cache.request('sword');cache._queue.join()
            target=cache.request('sword');self.assertTrue(target.is_file());self.assertEqual(preview.call_count,1)
    def test_change_between_queue_and_render_not_cached_under_old_key(self):
        cache=icons.IconCache()
        with patch.object(models,'CACHE_ROOT',self.root/'cache'),patch.object(models,'dependencies',return_value={'key':'a'*64}),patch.object(models,'preview',return_value=triangle_data('b'*64)),patch.object(models,'texture_path',return_value=self.texture):
            cache.request('sword');cache._queue.join()
            self.assertFalse((self.root/'cache'/'item-icons'/f"{icons.icon_key('a'*64)}.png").exists())
    def test_render_failure_is_returned_not_forever_pending(self):
        cache=icons.IconCache()
        with patch.object(models,'CACHE_ROOT',self.root/'cache'),patch.object(models,'dependencies',return_value={'key':'a'*64}),patch.object(models,'preview',side_effect=ValueError('bad geometry')):
            cache.request('sword');cache._queue.join()
            with self.assertRaisesRegex(models.PreviewUnavailable,'bad geometry'):cache.request('sword')


class LaunchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.module=self.root/'Modules'/'My Mod';self.module.mkdir(parents=True);(self.module/'module.ini').write_text('module_name = Test')
        (self.root/'mb_warband_wse2.exe').write_bytes(b'fixture-not-executable')
        self.now=0.0
    def sleep(self,delay):self.now+=delay
    def controller(self,job,timeout=2):
        return WarbandGameController(lambda args,cwd:job,timeout=timeout,clock=lambda:self.now,sleep=self.sleep)
    def test_module_with_spaces_is_single_argument(self):
        command=launch_command(self.root,self.module);self.assertEqual(command[1:],['--module','My Mod','--no-intro'])
    def test_no_silent_native_fallback(self):
        (self.root/'mb_warband_wse2.exe').unlink()
        with self.assertRaisesRegex(RuntimeError,'Neither mb_warband'):launch_command(self.root,self.module)
    def test_not_installed_never_launches_wrong_mod(self):
        outside=self.root/'project'/'Module';outside.mkdir(parents=True);(outside/'module.ini').write_text('')
        with self.assertRaisesRegex(RuntimeError,'not installed'):launch_command(self.root,outside.parent)
    def test_installed_link_uses_visible_module_name(self):
        project=self.root/'source';(project/'Module').mkdir(parents=True);(project/'Module'/'module.ini').write_text('')
        link=self.root/'Modules'/'Installed Alias'
        try:link.symlink_to(project/'Module',target_is_directory=True)
        except OSError:self.skipTest('directory symlinks unavailable')
        self.assertEqual(launch_command(self.root,project)[2],'Installed Alias')
    def test_window_required_before_running(self):
        job=FakeJob(window=None);controller=self.controller(job)
        with self.assertRaisesRegex(RuntimeError,'no game-sized window'):controller.launch(self.root,self.module)
        self.assertFalse(controller.status()['running']);self.assertTrue(job.terminated);self.assertTrue(job.closed)
    def test_early_exit_returns_error(self):
        job=FakeJob(pids=[]);controller=self.controller(job)
        with self.assertRaisesRegex(RuntimeError,'exited before'):controller.launch(self.root,self.module)
        self.assertFalse(controller.status()['running'])
    def test_child_handoff_and_stop_owned_job(self):
        job=FakeJob(pids=[100,200],window=200);controller=self.controller(job)
        result=controller.launch(self.root,self.module);self.assertTrue(result['windowObserved']);self.assertEqual(result['pid'],200)
        job.members=[200];self.assertTrue(controller.status()['running'])
        self.assertTrue(controller.stop()['stopped']);self.assertTrue(job.terminated);self.assertFalse(controller.status()['running'])
    def test_finished_process_returns_to_play(self):
        job=FakeJob();controller=self.controller(job);controller.launch(self.root,self.module);job.members=[]
        self.assertFalse(controller.status()['running']);self.assertTrue(job.closed)
    def test_job_factory_error_does_not_latch_running(self):
        def fail(*args):raise OSError('launch failed')
        controller=WarbandGameController(fail)
        with self.assertRaises(OSError):controller.launch(self.root,self.module)
        self.assertFalse(controller.status()['running'])


@unittest.skipUnless(os.name=="nt", "Windows host imports winreg")
class HostControllerTests(unittest.TestCase):
    def test_warband_delegation_does_not_change_other_game_processes(self):
        from desktop_host import HostApi
        import threading
        host=HostApi.__new__(HostApi)
        controller=SimpleNamespace(status=lambda:{'running':True,'pid':11},launch=lambda root,project:{'running':True,'module':project.name},stop=lambda:{'running':False})
        host._plugins={'warband':SimpleNamespace(game_process_factory=lambda:controller),'other':SimpleNamespace(process_names=())}
        host._lock=threading.RLock();host._game_processes={}
        host._projects=SimpleNamespace(snapshot=lambda key:{'current':str(Path.cwd()/'selected-mod')})
        with patch.object(host,'_game_executable',return_value=(Path.cwd(),Path.cwd()/'game.exe')):
            self.assertEqual(host.game_process_status('warband')['pid'],11)
            self.assertEqual(host.launch_game('warband')['module'],'selected-mod')
            self.assertFalse(host.stop_game('warband')['running'])
            self.assertFalse(host.game_process_status('other')['running'])
            process=SimpleNamespace(pid=22,poll=lambda:None)
            with patch('desktop_host.subprocess.Popen',return_value=process) as spawn:
                self.assertEqual(host.launch_game('other')['pid'],22)
                self.assertEqual(spawn.call_count,1)


class FakeJob:
    def __init__(self,pids=None,window=100):
        self.members=[100] if pids is None else pids;self.window=window;self.terminated=False;self.closed=False
    def pids(self):return self.members
    def window_pid(self):return self.window
    def terminate(self):self.terminated=True;self.members=[]
    def close(self):self.closed=True


@unittest.skipUnless(os.name=='nt','Windows job integration')
class WindowsJobTests(unittest.TestCase):
    def test_real_process_is_owned_and_stopped(self):
        job=WindowsGameJob([sys.executable,'-c','import time;time.sleep(60)'],Path.cwd())
        try:
            self.assertIn(job.process.pid,job.pids());self.assertIsNone(job.window_pid())
            job.terminate();job.process.wait(timeout=10)
            self.assertEqual(job.pids(),[])
        finally:
            job.terminate();job.close()


if __name__=='__main__':unittest.main()
