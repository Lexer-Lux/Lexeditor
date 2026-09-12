"""Signal Flare definition overlay tests. No game files or windows are used."""
from pathlib import Path
import os
import json
import re
import sys
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
VCVARS = Path(r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat")

def write_stubs(folder):
    for name, text in {
        "cfg.h":"extern bool enable_ff8_modern_controls;\n",
        "globals.h":"extern bool ff8;\n#define FF8_US_VERSION true\n",
        "common.h":"#include <cstdlib>\n#include <initializer_list>\n#define external_malloc std::malloc\n#define external_free std::free\n",
        "log.h":"inline void ffnx_warning(const char*,...){}\ninline void ffnx_trace(const char*,...){}\n",
        "patch.h":"inline void replace_call(unsigned,void*){}\ninline void replace_function(unsigned,void*){}\ninline void patch_code_dword(unsigned,unsigned){}\ninline void patch_code_byte(unsigned,unsigned char){}\n",
    }.items(): (folder/name).write_text(text)

class FlareItemTests(unittest.TestCase):
    def test_item_display_name_is_signal_flare(self):
        sys.path.insert(0, str(ROOT))
        from games.ff8.kernel_text import decode
        source=(ROOT/"games/ff8/ffnx_gameplay_extensions/ffnx-src/flare_item.h").read_text()
        body=re.search(r"item_name\[\]\s*=\s*\{([^}]+)\}",source).group(1)
        data=bytes(int(value.strip(),0) for value in body.split(","))
        self.assertEqual(data[-1],0)
        self.assertEqual(decode(data[:-1]),"Signal Flare")

    @unittest.skipUnless(os.name == "nt" and VCVARS.exists(), "Windows C++ Build Tools required")
    def test_menu_exit_owner_waits_for_item_cleanup_and_native_root_close(self):
        source=ROOT/"games/ff8/ffnx_gameplay_extensions/ffnx-src/lexeditor_ff8_flare_menu.cpp"
        code='#include <windows.h>\n#include "'+source.as_posix()+'"\n'+r''' 
bool ff8=true,enable_ff8_modern_controls=true;
unsigned calls=0;bool finish=false;
int __cdecl original(unsigned char *context) {
 ++calls;
 if(finish)*reinterpret_cast<unsigned char*>(0x01D77079)=0;
 return 123;
}
int main() {
 if(!VirtualAlloc(reinterpret_cast<void*>(0x01D70000),0x10000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE))return 1;
 if(!VirtualAlloc(reinterpret_cast<void*>(0x004C0000),0x10000,MEM_RESERVE|MEM_COMMIT,PAGE_EXECUTE_READWRITE))return 2;
 unsigned char jump[]={0x48,0xb8,0,0,0,0,0,0,0,0,0xff,0xe0};
 auto function=reinterpret_cast<std::uintptr_t>(&original);
 std::memcpy(jump+2,&function,8);std::memcpy(reinterpret_cast<void*>(0x004C0CF0),jump,12);
 unsigned char context[0x60]{};context[0x10]=7;
 auto &depth=*reinterpret_cast<unsigned char*>(0x01D77079);
 if(lexeditor_ff8_flare_menu_exit_request())return 3;
 installed=true;
 if(!lexeditor_ff8_flare_menu_exit_request() || lexeditor_ff8_flare_menu_exit_request())return 4;
 depth=2;
 if(lexeditor_ff8_flare_root_menu_controller(context)!=123 || context[0x10]!=7)return 5;
 depth=1;context[0x10]=3;
 lexeditor_ff8_flare_root_menu_controller(context);
 if(context[0x10]!=3 || lexeditor_ff8_flare_menu_exit_ready())return 6;
 context[0x10]=7;
 lexeditor_ff8_flare_root_menu_controller(context);
 if(context[0x10]!=21 || lexeditor_ff8_flare_menu_exit_ready())return 7;
 finish=true;context[0x10]=22;
 lexeditor_ff8_flare_root_menu_controller(context);
 if(context[0x10]!=22 || !lexeditor_ff8_flare_menu_exit_ready() || calls!=4)return 8;
 lexeditor_ff8_flare_menu_exit_reset();
 if(lexeditor_ff8_flare_menu_exit_ready() || !lexeditor_ff8_flare_menu_exit_request())return 9;
 enable_ff8_modern_controls=false;depth=1;context[0x10]=7;
 lexeditor_ff8_flare_root_menu_controller(context);
 if(context[0x10]!=21 || !lexeditor_ff8_flare_menu_exit_ready())return 10;
 lexeditor_ff8_flare_menu_exit_reset();
 if(!lexeditor_ff8_flare_menu_exit_request())return 11;
 return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix="lexeditor-flare-menu-") as temporary:
            folder=Path(temporary);write_stubs(folder)
            (folder/"check.cpp").write_text(code)
            (folder/"build.cmd").write_text(f'@echo off\ncall "{VCVARS}" >nul\ncl /nologo /EHsc /std:c++17 /I. check.cpp /Fe:check.exe\n')
            result=subprocess.run(["cmd","/c",str(folder/"build.cmd")],cwd=folder,capture_output=True,text=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            result=subprocess.run([str(folder/"check.exe")],capture_output=True,text=True,timeout=10,creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    @unittest.skipUnless(os.name == "nt" and VCVARS.exists(), "Windows C++ Build Tools required")
    def test_production_overlay_and_stock_text_lookup(self):
        source = ROOT / "games/ff8/ffnx_gameplay_extensions/ffnx-src/lexeditor_ff8_flare_item.cpp"
        code = '#include <windows.h>\n#include "' + source.as_posix() + '"\n#include "' + (source.parent/'flare_shop.h').as_posix() + '"\n' + r'''
#include <cstdio>
bool ff8=true, enable_ff8_modern_controls=true;
int file_size=199*4;
int request_result=1,requests=0,errors=0;
int __cdecl fake_request(){++requests;return request_result;}
void __cdecl fake_sound(int sound){if(sound==5)++errors;}
int __cdecl fake_loader(void **out,const char*) {
 *out=std::malloc(file_size);std::memset(*out,17,file_size);return file_size;
}
int main() {
 using namespace lexeditor_flare;
 unsigned char stock[stock_metadata_size], out[overlay_metadata_size+8];
 for(unsigned i=0;i<sizeof stock;++i) stock[i]=static_cast<unsigned char>(i);
 std::memset(out,0xa5,sizeof out);
 if(!make_metadata(stock,sizeof stock,out,overlay_metadata_size)) return 1;
 if(std::memcmp(stock,out,sizeof stock)) return 2;
 for(unsigned i=199;i<256;++i)
  if(out[i*4]!=10 || out[i*4+1] || out[i*4+2] || out[i*4+3]) return 3;
 for(unsigned i=overlay_metadata_size;i<sizeof out;++i) if(out[i]!=0xa5) return 4;
 std::memset(out,0xa5,sizeof out);
 if(make_metadata(stock,sizeof stock+4,out,sizeof out) ||
    make_metadata(stock,sizeof stock,out,overlay_metadata_size-1)) return 5;
 for(auto byte:out) if(byte!=0xa5) return 6;
 ShopRow shop[16]{};ShopView view;
 for(unsigned i=0;i<16;++i)shop[i]={static_cast<std::uint8_t>(i+1),100};
 if(!make_shop_view(shop,true,25,view) || !view.added || view.pages!=3) return 22;
 if(std::memcmp(view.rows.data(),shop,sizeof shop) || view.rows[16].id!=199 || view.rows[16].available!=25) return 23;
 for(unsigned i=17;i<198;++i)if(view.rows[i].id || view.rows[i].available) return 24;
 if(!make_shop_view(shop,false,0,view) || view.added || view.pages!=2 || view.rows[16].id) return 25;
 shop[15]={0,0};
 if(!make_shop_view(shop,true,25,view) || view.pages!=2 || view.rows[15].id!=199) return 26;
 auto before_view=view;shop[0].id=199;
 if(make_shop_view(shop,true,25,view) || std::memcmp(&view,&before_view,sizeof view)) return 27;
 shop[0].id=1;
 if(make_shop_view(shop,true,101,view) || std::memcmp(&view,&before_view,sizeof view)) return 28;
 if(!VirtualAlloc(reinterpret_cast<void*>(0x01CF0000),0x10000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE)) return 7;
 *reinterpret_cast<unsigned*>(0x01CF3EE4)=0x9000;
 *reinterpret_cast<unsigned*>(0x01CF3EE8)=0xa000;
 for(unsigned id=0;id<199;++id) {
  unsigned base=id<33 ? 0x01CF7778+id*24 : 0x01CF7A0C+id*4;
  *reinterpret_cast<unsigned short*>(base)=id*4;
  *reinterpret_cast<unsigned short*>(base+2)=id*4+2;
 }
 metadata_ready=true;
 for(unsigned id=0;id<199;++id)
  std::printf("%u %llu %llu\n",id,
   static_cast<unsigned long long>(reinterpret_cast<std::uintptr_t>(lexeditor_ff8_flare_item_name(id))),
   static_cast<unsigned long long>(reinterpret_cast<std::uintptr_t>(lexeditor_ff8_flare_item_description(id))));
 if(lexeditor_ff8_flare_item_name(199)!=item_name ||
    lexeditor_ff8_flare_item_description(199)!=item_description) return 8;
 for(unsigned id : {200u,255u,256u,0xffffffffu})
  if(*lexeditor_ff8_flare_item_name(id) || *lexeditor_ff8_flare_item_description(id)) return 9;
 *reinterpret_cast<unsigned short*>(0x01CF7778)=0xffff;
 if(reinterpret_cast<std::uintptr_t>(lexeditor_ff8_flare_item_name(0))!=0x01CFF84C) return 10;
 metadata_ready=false;
 if(*lexeditor_ff8_flare_item_name(199)) return 11;
 if(!VirtualAlloc(reinterpret_cast<void*>(0x00470000),0x50000,MEM_RESERVE|MEM_COMMIT,PAGE_EXECUTE_READWRITE)) return 12;
 // Redirect only the loader call to a fixture. The production wrapper owns
 // allocation, record preservation, replacement and collision handling.
 unsigned char jump[]={0x48,0xb8,0,0,0,0,0,0,0,0,0xff,0xe0};
 auto loader=reinterpret_cast<std::uintptr_t>(&fake_loader);
 std::memcpy(jump+2,&loader,8);std::memcpy(reinterpret_cast<void*>(0x004B96C0),jump,12);
 auto sound=reinterpret_cast<std::uintptr_t>(&fake_sound);
 std::memcpy(jump+2,&sound,8);std::memcpy(reinterpret_cast<void*>(0x004B92A0),jump,12);
 for(unsigned repeat=0;repeat<100;++repeat) {
  void *buffer=nullptr;
  if(lexeditor_ff8_flare_load_metadata(&buffer,"mitem.bin")!=1024 || !metadata_ready) return 13;
  for(unsigned i=0;i<796;++i) if(static_cast<unsigned char*>(buffer)[i]!=17) return 14;
  std::free(buffer);
  buffer=nullptr;
  if(lexeditor_ff8_flare_load_prices(&buffer,"price.bin")!=800) return 17;
  for(unsigned i=0;i<796;++i) if(static_cast<unsigned char*>(buffer)[i]!=17) return 18;
  const unsigned char price[]={20,0,10,0};
  if(std::memcmp(static_cast<unsigned char*>(buffer)+796,price,4)) return 19;
  std::free(buffer);
 }
 file_size=800;void *collision=nullptr;
 if(lexeditor_ff8_flare_load_metadata(&collision,"mitem.bin")!=800 || metadata_ready) return 15;
 for(unsigned i=0;i<800;++i) if(static_cast<unsigned char*>(collision)[i]!=17) return 16;
 std::free(collision);
 unsigned char menu[0x70]{};menu[0x65]=168;menu[0x10]=17;
 if(lexeditor_ff8_flare_menu_confirm(menu) || menu[0x10]!=17 || requests) return 29;
 metadata_ready=false;
 if(!lexeditor_ff8_flare_menu_request_bind(fake_request)) return 30;
 metadata_ready=true;menu[0x65]=199;
 if(!lexeditor_ff8_flare_menu_confirm(menu) || menu[0x10]!=0x70 || requests!=1 || errors) return 31;
 request_result=0;menu[0x10]=17;
 if(!lexeditor_ff8_flare_menu_confirm(menu) || menu[0x10]!=4 || requests!=2 || errors!=1) return 32;
 menu[0x65]=255;menu[0x10]=17;
 if(!lexeditor_ff8_flare_menu_confirm(menu) || menu[0x10]!=4 || requests!=2 || errors!=2) return 33;
 if(!lexeditor_ff8_flare_menu_request_bind(nullptr)) return 34;
 menu[0x65]=199;
 if(!lexeditor_ff8_flare_menu_confirm(menu) || requests!=2 || errors!=3) return 35;
 std::memset(out,0xa5,sizeof out);
 if(make_prices(stock,sizeof stock,out,799) || make_prices(stock,sizeof stock+4,out,sizeof out)) return 20;
 for(auto byte:out) if(byte!=0xa5) return 21;
 VirtualFree(reinterpret_cast<void*>(0x00470000),0,MEM_RELEASE);
 VirtualFree(reinterpret_cast<void*>(0x01CF0000),0,MEM_RELEASE);
 return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix="lexeditor-flare-item-") as temporary:
            folder=Path(temporary)
            write_stubs(folder)
            (folder/"check.cpp").write_text(code)
            (folder/"build.cmd").write_text(f'@echo off\ncall "{VCVARS}" >nul\ncl /nologo /EHsc /std:c++17 /I. check.cpp /Fe:check.exe\n')
            result=subprocess.run(["cmd","/c",str(folder/"build.cmd")],cwd=folder,capture_output=True,text=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            result=subprocess.run([str(folder/"check.exe")],capture_output=True,text=True,timeout=10,creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            rows=[tuple(map(int,line.split())) for line in result.stdout.splitlines()]
            self.assertEqual(len(rows),199)
            for item_id,name,description in rows:
                expected=0x01CF3E48+(0x9000 if item_id<33 else 0xa000)+item_id*4
                self.assertEqual((name,description),(expected,expected+2))

    @unittest.skipUnless(os.name == "nt" and VCVARS.exists(), "Windows C++ Build Tools required")
    def test_compiled_shop_guards_preserve_stock_and_refuse_new_ids(self):
        source = ROOT / "games/ff8/ffnx_gameplay_extensions/ffnx-src/lexeditor_ff8_flare_item.cpp"
        with tempfile.TemporaryDirectory(prefix="lexeditor-flare-shop-") as temporary:
            folder = Path(temporary)
            write_stubs(folder)
            (folder/"check.cpp").write_text('#include "'+source.as_posix()+'"\nbool ff8=true, enable_ff8_modern_controls=true;\nextern "C" __declspec(dllexport) void test_definitions_ready(int ready){metadata_ready=prices_ready=ready!=0;request_from_menu=ready?reinterpret_cast<MenuRequest>(1):nullptr;}\n')
            (folder/"shop.cpp").write_text('#include "'+(source.parent/'lexeditor_ff8_flare_shop.cpp').as_posix()+'"\n')
            (folder/"menu.cpp").write_text('#include "'+(source.parent/'lexeditor_ff8_flare_menu.cpp').as_posix()+'"\n')
            vcvars=VCVARS.with_name("vcvarsall.bat")
            (folder/"build.cmd").write_text(f'@echo off\ncall "{vcvars}" x86 >nul\ncl /nologo /LD /EHsc /std:c++17 /O2 /GS- /I. check.cpp shop.cpp menu.cpp /Fe:check.dll\n')
            result=subprocess.run(["cmd","/c",str(folder/"build.cmd")],cwd=folder,capture_output=True,text=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            worker = r'''
import sys,struct,json
sys.path.insert(0,sys.argv[2])
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *
p=pefile.PE(sys.argv[1]);base=p.OPTIONAL_HEADER.ImageBase
exports={e.name.decode():base+e.address for e in p.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
u=Uc(UC_ARCH_X86,UC_MODE_32)
u.mem_map(base,(p.OPTIONAL_HEADER.SizeOfImage+4095)&~4095)
u.mem_write(base,p.get_memory_mapped_image())
u.mem_map(0x400000,0x100000);u.mem_map(0x3000000,0x10000)
u.mem_write(0x4ffff0,b'\xc3')
u.mem_write(0x3000048,b'\x03')
stops={0x4ec7ac,0x4ec82b,0x4ec7dc,0x4ec30a,0x4ffff0,0x4f8a35,0x4fbf23}
def stop(uc,address,size,data):
 if address in stops:uc.emu_stop()
u.hook_add(UC_HOOK_CODE,stop)
count=0
for suffix,destination in [('buy',0x4ec7ac),('sell',0x4ec82b)]:
 entry=next(value for key,value in exports.items() if key.endswith('flare_shop_'+suffix+'_guard'))
 for item in range(256):
  u.reg_write(UC_X86_REG_EAX,0x12345678);u.reg_write(UC_X86_REG_ECX,item)
  u.reg_write(UC_X86_REG_ESI,0x3000000);u.reg_write(UC_X86_REG_ESP,0x3008000)
  u.emu_start(entry,0,count=100)
  assert u.reg_read(UC_X86_REG_EIP)==(destination if item<199 else 0x4ec7dc)
  assert u.reg_read(UC_X86_REG_EAX)==(item if item<199 else 0x12345678)
  assert u.reg_read(UC_X86_REG_ECX)==(3 if item<199 else item)
  count+=1
u.mem_map(0x1d20000,0x10000)
u.mem_write(0x1d2bb2c,struct.pack('<I',0x3000100))
u.mem_write(0x4b92a0,b'\xc3') # Refusal sound is the only native side call.
entry=next(value for key,value in exports.items() if key.endswith('flare_menu_dispatch'))
for item in (0,27,168,198,199,200,255):
 u.mem_write(0x3000065,bytes([item]));u.mem_write(0x3000010,b'\x11\0')
 u.reg_write(UC_X86_REG_ESI,0x3000000);u.reg_write(UC_X86_REG_ESP,0x3008000)
 u.reg_write(UC_X86_REG_EAX,0x12345678);u.reg_write(UC_X86_REG_EDI,0x87654321)
 u.emu_start(entry,0,count=1000)
 assert u.reg_read(UC_X86_REG_EIP)==(0x4f8a35 if item<199 else 0x4fbf23)
 assert u.reg_read(UC_X86_REG_ESP)==0x3008000
 assert u.reg_read(UC_X86_REG_EAX)==0x12345678
 assert u.reg_read(UC_X86_REG_EDI)==(0x3000100 if item<199 else 0x87654321)
 assert bytes(u.mem_read(0x3000010,2))==(b'\x11\0' if item<199 else b'\x04\0')
# Call the compiled runtime list owner. Only CRT byte-copy helpers are stubbed.
imports={};u.mem_map(0x20000000,0x10000)
for desc in p.DIRECTORY_ENTRY_IMPORT:
 for imp in desc.imports:
  address=0x20000000+len(imports)*16
  imports[address]=imp.name.decode() if imp.name else 'ordinal'
  u.mem_write(imp.address,struct.pack('<I',address))
def crt(uc,address,size,data):
 if address not in imports:return
 name=imports[address];esp=uc.reg_read(UC_X86_REG_ESP)
 ret,dst,arg,n=struct.unpack('<IIII',uc.mem_read(esp,16))
 if name in ('memcpy','memmove'):uc.mem_write(dst,bytes(uc.mem_read(arg,n)))
 elif name=='memset':uc.mem_write(dst,bytes([arg&255])*n)
 else:raise RuntimeError('Unexpected CRT call '+name)
 uc.reg_write(UC_X86_REG_EAX,dst);uc.reg_write(UC_X86_REG_ESP,esp+4);uc.reg_write(UC_X86_REG_EIP,ret)
u.hook_add(UC_HOOK_CODE,crt)
def call(suffix,*args):
 entry=next(value for key,value in exports.items() if key.endswith(suffix))
 u.mem_write(0x3008000,struct.pack('<'+'I'*(1+len(args)),0x4ffff0,*args))
 u.reg_write(UC_X86_REG_ESP,0x3008000)
 try:u.emu_start(entry,0,count=20000)
 except Exception as e:raise RuntimeError((suffix,hex(entry),hex(u.reg_read(UC_X86_REG_EIP)),hex(u.reg_read(UC_X86_REG_ESP)))) from e
 assert u.reg_read(UC_X86_REG_EIP)==0x4ffff0
 return u.reg_read(UC_X86_REG_EAX)
# Validate the compiled installers against the supported local EXE, then
# corrupt one instruction in each group. Validation must refuse without writes.
if len(sys.argv)>3:
 native=pefile.PE(sys.argv[3]).get_memory_mapped_image()[:0x100000]
 u.mem_write(0x400000,native);u.mem_write(0x4ffff0,b'\xc3')
 for suffix,address in [('definition',0x4a1c8e),('shop',0x4ebd55),('menu_exit',0x4c0b4b)]:
  assert call('flare_'+suffix+'_validate')==1
  old=bytes(u.mem_read(address,1));u.mem_write(address,bytes([old[0]^1]))
  before=bytes(u.mem_read(0x400000,0x100000))
  assert call('flare_'+suffix+'_validate')==0
  assert bytes(u.mem_read(0x400000,0x100000))==before
  u.mem_write(address,old)
rows=call('flare_shop_rows')
original=b''.join(bytes([i+1,100]) for i in range(16))
# Failed metadata/price load must hide the added listing.
u.mem_write(rows,original);call('flare_shop_refresh',1)
assert bytes(u.mem_read(rows,34))==original+bytes(2)
call('test_definitions_ready',1)
u.mem_map(0x1cf0000,0x10000);u.mem_map(0x1d80000,0x10000)
call('flare_transactions_enable',1)
full=b''.join(bytes([i,1]) for i in range(1,199))
u.mem_write(0x1cfe79c,full);u.mem_write(0x1d8d058,b'\0'+bytes([1])*198+b'\0')
assert call('flare_transaction_allowed',1)==0 # No native commit space.
assert call('flare_transaction_allowed',0)==1
u.mem_write(0x1cfe79c+394,bytes(2))
assert call('flare_transaction_allowed',1)==1
for suffix,destination in [('buy',0x4ec7ac),('sell',0x4ec82b)]:
 entry=next(value for key,value in exports.items() if key.endswith('flare_shop_'+suffix+'_guard'))
 u.reg_write(UC_X86_REG_EAX,0x12345678);u.reg_write(UC_X86_REG_ECX,199)
 u.reg_write(UC_X86_REG_ESI,0x3000000);u.reg_write(UC_X86_REG_ESP,0x3008000)
 u.mem_write(0x3000048,b'\x03');u.emu_start(entry,0,count=10000)
 assert u.reg_read(UC_X86_REG_EIP)==destination
 assert u.reg_read(UC_X86_REG_EAX)==199 and u.reg_read(UC_X86_REG_ECX)==3
 assert u.reg_read(UC_X86_REG_ESP)==0x3008000
u.mem_write(0x1cfe79c,bytes([199,1,199,1]))
assert call('flare_transaction_allowed',1)==0
# The authorized default offers one added listing in every stock shop.
for shop in range(20):
 u.mem_write(rows,original);call('flare_shop_refresh',shop)
 assert bytes(u.mem_read(rows,34))==original+bytes([199,100])
u.mem_write(rows,original)
assert call('flare_shop_configure',2,25)==1
call('flare_shop_refresh',1)
assert bytes(u.mem_read(rows,34))==original+bytes([199,25])
page_entry=next(value for key,value in exports.items() if key.endswith('flare_shop_pages'))
for shop,pages in [(1,3),(2,2)]:
 u.mem_write(rows,original);call('flare_shop_refresh',shop)
 u.reg_write(UC_X86_REG_ESI,0x3000000);u.reg_write(UC_X86_REG_EAX,0x12345678)
 u.reg_write(UC_X86_REG_ESP,0x3008000);u.emu_start(page_entry,0,count=100)
 assert bytes(u.mem_read(0x3000047,1))==bytes([pages])
 assert u.reg_read(UC_X86_REG_EAX)==0x12345678
 assert u.reg_read(UC_X86_REG_EIP)==0x4ec30a
assert bytes(u.mem_read(rows+32,2))==bytes(2)
print(json.dumps({'cases':count}))
'''
            (folder/"emulate.py").write_text(worker)
            from games.ff8 import paths
            private_exe=paths.GAME_ROOT/"FF8_EN.exe"
            command=[str(ROOT/".venv/Scripts/python.exe"),str(folder/"emulate.py"),str(folder/"check.dll"),str(ROOT/"_scratch/gf-spellbooks-test-deps")]
            if private_exe.is_file():command.append(str(private_exe))
            result=subprocess.run(command,capture_output=True,text=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual(json.loads(result.stdout),{"cases":512})

if __name__ == "__main__":
    unittest.main()
