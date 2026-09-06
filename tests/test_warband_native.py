"""Native launcher routing plus real Win32 control/process fixtures on Windows."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from games.warband.game_launch import launch_command, WarbandGameController, WindowsGameJob

class NativeRoutingTests(unittest.TestCase):
    def test_stock_executable_has_no_guessed_switches(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);mod=root/'Modules'/'A mod with spaces';mod.mkdir(parents=True)
            (mod/'module.ini').touch();(root/'mb_warband.exe').touch()
            self.assertEqual(launch_command(root,mod),[str((root/'mb_warband.exe').resolve())])
            (root/'mb_warband_wse2.exe').touch()
            with patch('games.warband.wse2_manager.require_managed'):
                self.assertEqual(launch_command(root,mod)[1:],['--module',mod.name,'--no-intro'])

    def test_native_must_complete_selection_before_readiness(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);mod=root/'Modules'/'Chosen';mod.mkdir(parents=True)
            (mod/'module.ini').touch();(root/'mb_warband.exe').touch()
            now=[0.0];calls=[]
            class Job:
                alive=True
                def pids(self):return [51] if self.alive else []
                def window_pid(self):calls.append('window');return 51
                def terminate(self):self.alive=False
                def close(self):pass
            class Launcher:
                def __init__(self,job,module):self.n=0;calls.append(module)
                def advance(self):self.n+=1;calls.append('select');return self.n>2
            job=Job();controller=WarbandGameController(lambda *args:job,clock=lambda:now[0],sleep=lambda n:now.__setitem__(0,now[0]+n),native_factory=Launcher)
            result=controller.launch(root,mod)
            self.assertEqual(result['module'],'Chosen');self.assertTrue(result['windowObserved'])
            self.assertEqual(calls[:4],['Chosen','select','select','select'])
            self.assertFalse(controller.stop()['running'])

@unittest.skipUnless(os.name=='nt','real Win32 fixture')
class NativeWindowTests(unittest.TestCase):
    def test_real_module_selection_play_and_stop(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);mod=root/'Modules'/'Chosen Module';mod.mkdir(parents=True)
            (mod/'module.ini').touch();(root/'mb_warband.exe').touch()
            report=root/'selected.json';fixture=Path(__file__).parent/'fixtures'/'warband_launcher_window.py'
            def factory(command,cwd):
                return WindowsGameJob([sys.executable,str(fixture),str(report),mod.name],cwd)
            controller=WarbandGameController(factory,timeout=10)
            try:
                result=controller.launch(root,mod)
                self.assertTrue(result['windowObserved'])
                self.assertEqual(json.loads(report.read_text()),{'selected':mod.name,'realPlay':True})
                self.assertTrue(controller.stop()['stopped'])
                self.assertFalse(controller.status()['running'])
            finally:
                controller.stop()

    def test_missing_module_never_activates_decoy_or_another_window(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);mod=root/'Modules'/'Missing';mod.mkdir(parents=True)
            (mod/'module.ini').touch();(root/'mb_warband.exe').touch()
            fixture=Path(__file__).parent/'fixtures'/'warband_launcher_window.py';report=root/'selected.json'
            unrelated=subprocess.Popen([sys.executable,str(fixture),str(root/'unrelated.json'),mod.name])
            jobs=[]
            def factory(command,cwd):
                job=WindowsGameJob([sys.executable,str(fixture),str(report),mod.name,'missing'],cwd);jobs.append(job);return job
            controller=WarbandGameController(factory,timeout=3)
            try:
                with self.assertRaisesRegex(RuntimeError,'no game-sized window'):
                    controller.launch(root,mod)
                self.assertFalse(report.exists());self.assertFalse((root/'unrelated.json').exists())
                self.assertIsNone(unrelated.poll());self.assertFalse(controller.status()['running'])
            finally:
                controller.stop();unrelated.terminate();unrelated.wait(timeout=5)

    def test_immediate_child_handoff_stays_in_job(self):
        with tempfile.TemporaryDirectory() as name:
            report=Path(name)/'pid.txt'
            code='import subprocess,sys,pathlib;p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"]);pathlib.Path(sys.argv[1]).write_text(str(p.pid))'
            job=WindowsGameJob([sys.executable,'-c',code,str(report)],Path(name))
            try:
                deadline=time.monotonic()+5
                while not report.exists() and time.monotonic()<deadline:time.sleep(.05)
                self.assertTrue(report.exists())
                child=int(report.read_text());self.assertIn(child,job.pids())
                job.terminate()
                while job.pids() and time.monotonic()<deadline:time.sleep(.05)
                self.assertEqual(job.pids(),[])
            finally:
                job.terminate();job.close()

if __name__=='__main__':unittest.main()
