"""Execute the real satchel category predicate to test datastore-only tab injection."""
import argparse,os,re,shutil,subprocess,tempfile
from pathlib import Path
from research_rdr2_horse_feed_dispatch import functions
PRELUDE=r'''
using Hash=unsigned;using BOOL=bool;
struct {int f_17=0;} Global_1935689;
struct {struct {int f_1=0;} f_16855;} Global_1914319;
bool func_27(bool){return false;}bool func_161(Hash,int){return true;}
bool func_757(Hash){return false;}bool func_759(Hash,int){return true;}
int func_259(Hash,int){return 0;}bool func_111(Hash,int){return true;}
bool func_384(Hash,int){return true;}bool func_269(Hash,int){return true;}
bool func_758(Hash){return true;}Hash joaat(const char*){return 999;}
'''
TESTS=r'''
int main(){
 // Valid owned-item fixture with every tag predicate allowed. Unknown category
 // still rejects it; ownership/tags cannot make an added category work.
 for(int category:{-1666604090,-1559802791,-1268291907,-156634416,-96974025,1061777683,1561961676})if(!func_519(123,category,false))return 1;
 for(int category:{123456,234567,-345678})if(func_519(123,category,false))return 2;
 return 0;
}
'''
def main():
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=Path('C:/RDR2Mod/_downloads/RDR2-Decompiled-Scripts-1491.50/1491.50/script_rel/satchel_ui_event_handler.ysc.c'));a=p.parse_args()
 f=functions(a.source.read_text(encoding='utf-8-sig'));body=f['func_519']['body'].strip();body=body[:body.rfind('}')].rstrip()
 assert body.endswith('return false;')
 for name,needle in [('func_235','func_519(panParam0->f_4, iParam1, false)'),('func_13','func_94(&unk, &unk3, iParam0)'),('func_94','func_235(panParam1, iParam2, true)'),('func_207','i < 11'),('func_210','num >= 2')]:assert needle in f[name]['body'],name
 signature='BOOL func_519(Hash hParam0,int iParam1,BOOL bParam2){\n'
 variants={'production':body,'invent-dynamic-fallback':body[:-len('return false;')]+'return true;'}
 compiler=shutil.which('g++') or shutil.which('clang++');vcvars=Path('C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat')
 with tempfile.TemporaryDirectory(prefix='lex-satchel-test-') as temp:
  folder=Path(temp)
  for name,variant in variants.items():
   cpp=folder/'test.cpp';exe=folder/'test.exe';cpp.write_text('#include <initializer_list>\n'+PRELUDE+signature+variant+'\n}\n'+TESTS)
   if compiler:command=[compiler,'-std=c++17',str(cpp),'-o',str(exe)]
   else:
    batch=folder/'compile.cmd';batch.write_text(f'@echo off\ncall "{vcvars}" >nul\ncl /nologo /EHsc /std:c++17 "{cpp}" /Fe:"{exe}" /Fo:"{folder / "test.obj"}"\n');command=['cmd','/d','/c',str(batch)]
   result=subprocess.run(command,cwd=folder,capture_output=True,text=True,timeout=60)
   if result.returncode:raise RuntimeError(result.stdout+result.stderr)
   result=subprocess.run([str(exe)],cwd=folder,timeout=10)
   assert (result.returncode==0)==(name=='production'),(name,result.returncode)
   print(('PASS ' if name=='production' else 'REJECTED ')+name)
 print('Actual category predicate rejects injected IDs despite valid ownership and allowed tags; native-tab rendering itself remains untested')
if __name__=='__main__':main()
