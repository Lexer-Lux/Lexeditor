"""Execute casing acquisition against inventory failures, without a game process."""
from pathlib import Path
import argparse,os,shutil,subprocess,tempfile
PRELUDE=r'''
#include <map>
using Hash=unsigned;
std::map<Hash,int> amounts;int adds=0;bool available=true,addWorks=true,flag=true,hideAfter=false;
int INVENTORY_ITEM_COUNT(Hash item){return available?amounts[item]:-1;}
bool INVENTORY_ADD(Hash item,int){++adds;if(addWorks)++amounts[item];if(hideAfter)available=false;return flag;}
#define CHECK(x) do{if(!(x))return __LINE__;}while(0)
'''
TESTS=r'''
int main(){using namespace CasingAcquisition;State a,b;
 addWorks=false;CHECK(grant(a,1)==Result::Failed);CHECK(amounts[1]==0&&adds==1);
 addWorks=true;flag=false;CHECK(grant(a,1)==Result::Granted);CHECK(amounts[1]==1&&adds==2);
 available=false;CHECK(grant(a,1)==Result::Failed);CHECK(adds==2);
 available=true;hideAfter=true;CHECK(grant(a,1)==Result::Pending);CHECK(adds==3&&amounts[1]==2);
 for(int i=0;i<10;++i)CHECK(grant(a,1)==Result::Pending);CHECK(adds==3);
 // Two live casing owners cannot share or duplicate an unresolved grant.
 CHECK(grant(b,1)==Result::Pending);CHECK(b.token==0&&adds==3);
 available=true;CHECK(grant(b,2)==Result::Pending);CHECK(adds==3);
 CHECK(grant(a,1)==Result::Granted);CHECK(adds==3);
 hideAfter=false;CHECK(grant(b,1)==Result::Granted);CHECK(adds==4&&amounts[1]==3);
 // Original prop cleanup, then a different prop of the SAME item.
 hideAfter=true;CHECK(grant(a,1)==Result::Pending);auto old=a.token;cancel(a);
 available=true;hideAfter=false;CHECK(grant(b,1)==Result::Granted);CHECK(adds==6&&amounts[1]==5);
 // Reusing the original state after cleanup is a fresh transaction.
 hideAfter=true;CHECK(grant(a,1)==Result::Pending);CHECK(a.token!=old);cancel(a);
 available=true;hideAfter=false;CHECK(grant(b,2)==Result::Granted);CHECK(adds==8&&amounts[2]==1);
 return 0;
}
'''
def main():
 p=argparse.ArgumentParser();p.add_argument('--runtime-root',type=Path,default=Path('C:/RDR2Mod'));a=p.parse_args()
 source=(a.runtime_root/'GameplayTweaks/modules/casing_acquisition.h').read_text(encoding='utf-8-sig')
 caller=(a.runtime_root/'GameplayTweaks/modules/items_casings.cpp').read_text(encoding='utf-8-sig')
 assert caller.index('CasingAcquisition::grant(casing.acquisition, casing.item)')<caller.index('if (acquisition != CasingAcquisition::Result::Granted)')<caller.index('CASING_FEED(',caller.index('CasingAcquisition::grant(casing.acquisition, casing.item)'))
 variants={'production':source,'trust-native-flag':source.replace('INVENTORY_ADD(item,1);','if(!INVENTORY_ADD(item,1))return Result::Failed;'),'forget-owner':source.replace('if(pendingOwner && pendingOwner!=state.token)return Result::Pending;',''),'false-success':source.replace('after>state.baseline','after>=state.baseline'),'lost-cleanup':source.replace('if(pendingOwner==state.token)pendingOwner=0;state={};','state={};')}
 compiler=shutil.which('g++') or shutil.which('clang++');vcvars=Path('C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat')
 with tempfile.TemporaryDirectory(prefix='lex-casing-test-') as temp:
  folder=Path(temp)
  for name,code in variants.items():
   assert name=='production' or code!=source
   cpp=folder/'test.cpp';exe=folder/'test.exe';cpp.write_text(PRELUDE+code+TESTS)
   if compiler:cmd=[compiler,'-std=c++17',str(cpp),'-o',str(exe)]
   else:
    batch=folder/'compile.cmd';batch.write_text(f'@echo off\ncall "{vcvars}" >nul\ncl /nologo /EHsc /std:c++17 "{cpp}" /Fe:"{exe}" /Fo:"{folder / "test.obj"}"\n');cmd=['cmd','/d','/c',str(batch)]
   result=subprocess.run(cmd,cwd=folder,capture_output=True,text=True,timeout=60)
   if result.returncode:raise RuntimeError(result.stdout+result.stderr)
   result=subprocess.run([str(exe)],cwd=folder,capture_output=True,timeout=10)
   assert (result.returncode==0)==(name=='production'),(name,result.returncode)
   print(('PASS ' if name=='production' else 'REJECTED ')+name)
if __name__=='__main__':main()
