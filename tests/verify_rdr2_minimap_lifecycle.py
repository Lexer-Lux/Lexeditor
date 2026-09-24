"""Execute production minimap ownership with fake native readbacks, without a game."""
from pathlib import Path
import argparse
import subprocess
import tempfile

PRELUDE = r'''
#include <unordered_set>
#include <vector>
#include <cstdint>
#include <cstdio>
#define assert(x) do { if (!(x)) return __LINE__; } while(0)
#define sprintf_s std::snprintf
using Ped=int; using Blip=int; using Hash=int; using DWORD=uint32_t; using Void=int;
constexpr bool TRUE=true,FALSE=false;
enum class ReconDisposition {Enemy, Ally};
struct {int partMinimap=1;} g_reconCachedSettings;
bool enabled=true; int policeOn=0,policeOff=0,adds=0,removes=0;
std::unordered_set<int> live{1,2,3,4}, tagged, hidden, blips{12,13,14};
std::vector<int> snapshot{2,3,4};
Hash joaat(const char*){return 1;}
bool reconTaggedOnlyMinimapEnabled(){return enabled;}
bool isReconTagged(int p){return tagged.count(p);}
ReconDisposition reconDispositionFor(int,int){return ReconDisposition::Enemy;}
void reconLog(const char*){}
namespace ENTITY {bool DOES_ENTITY_EXIST(int p){return live.count(p);}}
namespace PED {
bool IS_PED_DEAD_OR_DYING(int,bool){return false;}
bool IS_PED_HUMAN(int p){return p==2;}
}
namespace PLAYER {
void SET_POLICE_RADAR_BLIPS(bool b){if(b)++policeOn;else ++policeOff;}
int PLAYER_ID(){return 0;} int _GET_SADDLE_HORSE_FOR_PLAYER(int){return 4;}
}
namespace MAP {
bool DOES_BLIP_EXIST(int b){return blips.count(b);}
int GET_BLIP_FROM_ENTITY(int p){return p+10;}
}
template<class T> T invoke(uint64_t,int b,int){hidden.erase(b);++removes;return {};}
void ADD_BLIP_MODIFIER(int b,int){hidden.insert(b);++adds;}
int sharedWorldPedSnapshot(int* out,int n){int i=0;for(int p:snapshot)if(i<n)out[i++]=p;return i;}
'''
TESTS = r'''
int main(){
 suppressUnmarkedHostileBlips(1,100);
 assert(hidden.count(12) && hidden.count(13) && !hidden.count(14));
 assert(adds==2 && policeOff==1); // Humans, wolves, saddle-horse exemption.
 suppressUnmarkedHostileBlips(1,101);assert(adds==2 && policeOff==1);
 suppressUnmarkedHostileBlips(1,350);assert(adds==2 && policeOff==2);
 tagged.insert(3);suppressUnmarkedHostileBlips(1,600);
 assert(!hidden.count(13) && hidden.count(12) && removes==1);
 enabled=false;suppressUnmarkedHostileBlips(1,601);
 assert(hidden.empty() && policeOn==1 && removes==2);
 suppressUnmarkedHostileBlips(1,602);assert(policeOn==1 && removes==2);
 enabled=true;suppressUnmarkedHostileBlips(1,603);
 assert(hidden.count(12) && adds==3); // Re-enable must not wait on old deadline.
 releaseReconMinimapSuppression();assert(hidden.empty() && policeOn==2);
 releaseReconMinimapSuppression();assert(policeOn==2 && removes==3);
 g_reconCachedSettings.partMinimap=0;suppressUnmarkedHostileBlips(1,604);
 assert(hidden.empty() && policeOn==2);
 g_reconCachedSettings.partMinimap=1;suppressUnmarkedHostileBlips(1,605);
 assert(hidden.count(12));
 blips.erase(12);suppressUnmarkedHostileBlips(1,900);
 assert(g_reconSuppressedHostileBlips.empty());
}
'''

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--runtime-root', type=Path, default=Path('C:/RDR2Mod'))
    args=parser.parse_args()
    source=(args.runtime_root/'GameplayTweaks/modules/recon.cpp').read_text('utf-8')
    start=source.index('static const Hash kReconHiddenBlipModifier')
    # Only the ownership helpers are required; later unrelated helpers precede mark.
    stop=source.index('\n}',source.index('static void suppressUnmarkedHostileBlips',start))+2
    code=source[start:stop]
    update=source[source.index('static void updateReconTagging'):]
    assert 'if (!g_reconTaggingEnabled) {\n\t\t\tclearReconTargets();\n\t\t\treleaseReconMinimapSuppression();' in update
    variants={'production':code,
      'no-release':code.replace('restoreAllSuppressedReconBlips();',''),
      'stale-deadline':code.replace('\n\tg_reconNextHostileSweep = 0;',''),
      'animals-excluded':code.replace('other == saddleHorse ||','!PED::IS_PED_HUMAN(other) || other == saddleHorse ||'),
      'repeat-modifier':code.replace('if (g_reconSuppressedHostileBlips.count(blip)) continue;','')}
    vcvars=Path('C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat')
    with tempfile.TemporaryDirectory(prefix='lex-minimap-test-') as temporary:
        folder=Path(temporary).resolve()
        assert folder.parent==Path(tempfile.gettempdir()).resolve()
        for name,body in variants.items():
            assert name=='production' or body!=code
            cpp=folder/'test.cpp'; exe=folder/'test.exe'; batch=folder/'compile.cmd'
            # Production uses MSVC's sized-array sprintf_s overload.
            cpp.write_text((PRELUDE+body+TESTS).replace('sprintf_s(line,','sprintf_s(line, sizeof(line),'),'utf-8')
            batch.write_text(f'@echo off\ncall "{vcvars}" >nul\ncl /nologo /EHsc /std:c++17 "{cpp}" /Fe:"{exe}" /Fo:"{folder / "test.obj"}"\n','utf-8')
            result=subprocess.run(['cmd','/d','/c',str(batch)],cwd=folder,capture_output=True,text=True,timeout=60)
            assert result.returncode==0,result.stdout+result.stderr
            run=subprocess.run([str(exe)],cwd=folder,capture_output=True,timeout=10)
            assert (run.returncode==0)==(name=='production'),(name,run.returncode)
            print(('PASS ' if name=='production' else 'REJECTED ')+name)
    print('Production minimap lifecycle checked. In-game marker visibility remains unverified.')

if __name__=='__main__':main()
