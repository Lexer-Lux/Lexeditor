"""Execute the real cigarette-card conversion against controlled inventory failures."""
from pathlib import Path
import os
import argparse
import shutil
import subprocess
import tempfile

PRELUDE=r'''
#include <map>
#include <string>
#include <cstdio>
using Hash=unsigned;
std::map<std::string,Hash> names;std::map<Hash,int> counts;
long long mailed=0;bool addWorks=true,removeOriginalWorks=true,rollbackWorks=true,nativeFlag=true;
Hash currentOriginal=0,currentDuplicate=0;int grants=0;
Hash joaat(const char*s){auto &h=names[s];if(!h)h=(unsigned)names.size();return h;}
long long* getGlobalPtr(int){return &mailed;}
int INVENTORY_ITEM_COUNT(Hash h){return counts[h];}
bool INVENTORY_ADD(Hash h,int n){if(addWorks){counts[h]+=n;++grants;}return nativeFlag;}
bool INVENTORY_REMOVE(Hash h,int n){bool works=h==currentDuplicate?rollbackWorks:removeOriginalWorks;if(works&&counts[h]>=n)counts[h]-=n;return nativeFlag;}
#define CHECK(c) do { if(!(c)) return __LINE__; } while(0)
'''
TESTS=r'''
int main(){using namespace DuplicateCigaretteCards;
 initialize();
 for(const auto &set:g_sets)for(Hash card:set.cards)counts[card]=1;
 update(true);CHECK(grants==0);
 mailed=4095;update(true);CHECK(grants==144);
 for(const auto &set:g_sets){CHECK(counts[set.duplicate]==12);for(Hash card:set.cards)CHECK(counts[card]==0);}
 counts.clear();grants=0;currentOriginal=g_sets[0].cards[0];currentDuplicate=g_sets[0].duplicate;
 counts[currentOriginal]=1;addWorks=false;CHECK(!convertOne(currentOriginal,currentDuplicate));CHECK(counts[currentOriginal]==1&&counts[currentDuplicate]==0);
 addWorks=true;nativeFlag=false;CHECK(convertOne(currentOriginal,currentDuplicate));CHECK(counts[currentOriginal]==0&&counts[currentDuplicate]==1);
 counts[currentOriginal]=1;counts[currentDuplicate]=0;nativeFlag=true;removeOriginalWorks=false;rollbackWorks=false;
 CHECK(!convertOne(currentOriginal,currentDuplicate));CHECK(counts[currentOriginal]==1&&counts[currentDuplicate]==1);
 int previousGrants=grants;
 for(int i=0;i<10;++i)CHECK(!convertOne(currentOriginal,currentDuplicate));
 CHECK(grants==previousGrants&&counts[currentOriginal]==1&&counts[currentDuplicate]==1);
 rollbackWorks=true;update(false);CHECK(counts[currentDuplicate]==0&&counts[currentOriginal]==1);
 removeOriginalWorks=true;CHECK(convertOne(currentOriginal,currentDuplicate));CHECK(counts[currentOriginal]==0&&counts[currentDuplicate]==1);
 return 0;
}
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root',type=Path,default=Path('C:/RDR2Mod'))
    args=parser.parse_args()
    source=(args.runtime_root/'GameplayTweaks/modules/duplicate_cigarette_cards.cpp').read_text(encoding='utf-8')
    variants={'production':source,
      'skip-rollback-barrier':source.replace('if (!settlePendingConversion()) return false;',''),
      'ignore-mailing':source.replace('if ((mailedSets & set.mailedMask) == 0) continue;',''),
      'trust-return-flag':source.replace('INVENTORY_REMOVE(original, 1);','if (!INVENTORY_REMOVE(original, 1)) return false;')}
    compiler=shutil.which('g++') or shutil.which('clang++')
    vcvars=Path('C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat')
    with tempfile.TemporaryDirectory(prefix='lex-card-test-') as temp:
        folder=Path(temp)
        for name,code in variants.items():
            assert name=='production' or code!=source
            cpp=folder/'test.cpp';exe=folder/('test.exe' if os.name=='nt' else 'test')
            compat='' if not compiler else '#define sprintf_s(buf,...) std::snprintf(buf,sizeof(buf),__VA_ARGS__)\n'
            cpp.write_text(PRELUDE+compat+code+TESTS,encoding='utf-8')
            if compiler: command=[compiler,'-std=c++17',str(cpp),'-o',str(exe)]
            else:
                batch=folder/'compile.cmd'
                batch.write_text(f'@echo off\ncall "{vcvars}" >nul\ncl /nologo /EHsc /std:c++17 "{cpp}" /Fe:"{exe}" /Fo:"{folder / "test.obj"}"\n',encoding='utf-8')
                command=['cmd','/d','/c',str(batch)]
            result=subprocess.run(command,cwd=folder,capture_output=True,text=True,timeout=60)
            if result.returncode:raise RuntimeError(result.stdout+result.stderr)
            result=subprocess.run([str(exe)],cwd=folder,capture_output=True,timeout=10)
            assert (result.returncode==0)==(name=='production'),(name,result.returncode)
            print(('PASS ' if name=='production' else 'REJECTED ')+name)
    print('All12 set states and rollback failures tested; game acceptance remains unverified')


if __name__=='__main__':main()
