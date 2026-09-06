"""Compile the production policy and execute it with native camera follow."""
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_ff8_world_camera_native_seam import EXE, follow_trace

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / '_scratch' / 'modern-camera-core-test'


def main():
    WORK.mkdir(exist_ok=True)
    header = ROOT / 'games/ff8/ffnx_modern_controls/camera_axis.h'
    cpp = '#include "' + header.as_posix() + '"\n' + r'''
#include <cstdio>
#include <cassert>
int main() {
  for(int raw=0; raw<=255; ++raw) {
    int rem=0, sum=0;
    for(int i=0;i<87;++i) sum+=lexeditor_camera::yaw_step(raw,rem);
    const int a=std::clamp(raw-128,-127,127), mag=a<0?-a:a;
    assert(sum == (mag<=40 ? 0 : (a<0?-1:1)*(mag-40)*16));
    int pitch_rem=0, pitch_sum=0;
    for(int i=0;i<87;++i) pitch_sum+=lexeditor_camera::pitch_step(raw,pitch_rem);
    assert(pitch_sum == sum);
  }
  {
    lexeditor_camera::ManualPitch pitch;
    int value=-112;
    // Raw Y=0 moves toward the native lower pitch bound and must clamp there.
    for(int i=0;i<64;++i) value=pitch.update(value,value,0,false,false);
    assert(value == -0x200 && pitch.engaged);
    // Center holds a manually chosen angle against native follow.
    for(int i=0;i<64;++i) value=pitch.update(value,-112,128,false,false);
    assert(value == -0x200);
    // Native shoulder handling temporarily owns the angle.
    value=pitch.update(value,-112,128,true,false);
    assert(value == -112);
    // A world-state reset relinquishes manual ownership.
    value=pitch.update(value,-256,128,false,true);
    assert(value == -256 && !pitch.engaged);
    // Opposite deflection reaches but never exceeds the upper native bound.
    for(int i=0;i<64;++i) value=pitch.update(value,value,255,false,false);
    assert(value == 0);
  }
  lexeditor_camera::ManualYaw policy;
  unsigned before,native; int raw,shoulder,reset;
  while(std::scanf("%u %u %d %d %d",&before,&native,&raw,&shoulder,&reset)==5) {
    std::printf("%u\n",policy.update(before,native,raw,shoulder!=0,reset!=0));
    std::fflush(stdout);
  }
}
'''
    (WORK / 'core.cpp').write_text(cpp)
    (WORK / 'build.cmd').write_text('@echo off\ncall "C:\\Program Files (x86)\\Microsoft Visual Studio\\2022\\BuildTools\\VC\\Auxiliary\\Build\\vcvarsall.bat" x86 >nul\ncl /nologo /EHsc /std:c++17 /Od core.cpp /Fe:core.exe\n')
    build = subprocess.run(['cmd', '/c', str(WORK / 'build.cmd')], cwd=WORK, capture_output=True, text=True)
    assert build.returncode == 0, build.stdout + build.stderr
    exe = EXE.read_bytes()
    for vehicle in (False, True):
        for options in ({}, {'center_after':100}, {'center_after':100, 'reset_at':110},
                        {'shoulder':127}, {'shoulder':-127}, {'delta':0}):
            with subprocess.Popen([str(WORK/'core.exe')], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, text=True) as core:
                actual = follow_trace(exe, vehicle, manual_policy=True, core=core, **options)
                core.stdin.close()
                assert core.wait() == 0
            expected = follow_trace(exe, vehicle, manual_policy=True, **options)
            assert actual == expected, (vehicle, options)
    print('Compiled production camera policy: 256 axis sweeps and 3600 native follow updates passed')


if __name__ == '__main__':
    main()
