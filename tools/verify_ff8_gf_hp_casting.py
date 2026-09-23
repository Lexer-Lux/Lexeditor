"""Execute GF HP Casting hooks against the supported FF8 executable, headless."""
from pathlib import Path
import hashlib,struct,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *
from plugins.ff8 import gf_hp_casting as casting,gf_hp_casting_asm as a,max_spell
from plugins.ff8.gf_hp_casting_code import SOURCE_SHA256
assert hashlib.sha256(repr(a.SOURCES).encode()).hexdigest()==SOURCE_SHA256, "Reassemble changed GF HP Casting source"
EXE=Path(r'D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe')
raw=EXE.read_bytes()
assert hashlib.sha256(raw).hexdigest()=='064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570'
with EXE.open('rb') as f:casting.verify_executable(f)
image=pefile.PE(data=raw).get_memory_mapped_image()
STACK=0x2908000
LIST=0x1cff082
HPS=0x1cfdcba

def machine(actor=0,gf=0,hp=100,cost=30,mask=None):
 u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0x400000,0x2600000);u.mem_write(0x400000,image)
 for patch in (max_spell.build_hext(True,10),casting.build_hext(True,[cost]*57)):
  for line in patch.splitlines():
   if ' = ' in line:
    addr,data=line.split(' = ');u.mem_write(int(addr,16),bytes.fromhex(data))
 u.reg_write(UC_X86_REG_ESP,STACK);u.reg_write(UC_X86_REG_EBP,0)
 u.mem_write(0x1d768d0,struct.pack('<I',0x4c8820));u.mem_write(0x1d768eb,bytes([actor]))
 u.mem_write(0x1cfe74c+actor,bytes([actor]));u.mem_write(0x1cfe140+actor*152,struct.pack('<H',(1<<gf) if mask is None else mask))
 u.mem_write(0x1cfdcb9+gf*68,b'\x01');u.mem_write(HPS+gf*68,struct.pack('<H',hp))
 u.mem_write(0x1d768f4,b'\x02');u.mem_write(LIST+actor*0x1d0,bytes([1,1,0,0,0,2,1,0,0,0]))
 return u

def run(u,start,stops):
 reached=[]
 def hook(vm,address,size,data):
  if address in stops:reached.append(address);vm.emu_stop()
  # Native cancel-queue and error-sound I/O are isolated from the fixture.
  if address in (0x4bb570,0x4a9780):
   sp=vm.reg_read(UC_X86_REG_ESP);ret=struct.unpack('<I',vm.mem_read(sp,4))[0]
   vm.reg_write(UC_X86_REG_ESP,sp+4);vm.reg_write(UC_X86_REG_EIP,ret)
 handle=u.hook_add(UC_HOOK_CODE,hook);u.emu_start(start,0,count=10000);u.hook_del(handle)
 assert len(reached)==1,(hex(start),reached)
 return reached[0]

for actor in range(3):
 for gf in range(16):
  for hp,queued,expected in ((100,0,True),(29,0,False),(30,0,True),(60,1,True),(59,1,False),(90,2,True),(89,2,False)):
   u=machine(actor,gf,hp);u.mem_write(0x1d76904,bytes([queued]))
   u.reg_write(UC_X86_REG_EAX,LIST+actor*0x1d0);u.reg_write(UC_X86_REG_ESI,0)
   assert run(u,0x4fe2b9,{0x4fe2c3,0x4fe2e5})==(0x4fe2c3 if expected else 0x4fe2e5)
   assert struct.unpack('<H',u.mem_read(HPS+gf*68,2))[0]==hp
for mask in (0,3):
 u=machine(mask=mask);u.reg_write(UC_X86_REG_EAX,LIST)
 assert run(u,0x4fe2b9,{0x4fe2c3,0x4fe2e5})==0x4fe2e5
# Different spells in one queued Double/Triple charge their own costs.
for hp,expected in ((100,30),(70,0),(69,69)):
 u=machine(hp=hp);u.mem_write(a.COSTS+4,struct.pack('<H',40));u.mem_write(0x1d76904,bytes([1,1]))
 reached=run(u,0x4fe652,{0x4fe658,0x4fe768})
 assert reached==(0x4fe658 if hp>=70 else 0x4fe768)
 assert struct.unpack('<H',u.mem_read(HPS,2))[0]==expected
 assert bytes(u.mem_read(LIST,10))==bytes([1,1,0,0,0,2,1,0,0,0])
 if hp<70:assert bytes(u.mem_read(0x1d76904,32))==bytes(32)
# Use the live HP copy during a summon, preserving the stale saved value.
u=machine(hp=900);u.mem_write(0x1cff01c,bytes([1,0x40]));u.mem_write(0x1cff018,struct.pack('<H',50));u.mem_write(0x1d76904,b'\x01')
assert run(u,0x4fe652,{0x4fe658,0x4fe768})==0x4fe658
assert struct.unpack('<H',u.mem_read(0x1cff018,2))[0]==20
assert struct.unpack('<H',u.mem_read(HPS,2))[0]==900
# Item/other controllers retain their own native permission and debit paths.
u=machine(mask=0);u.mem_write(0x1d768d0,struct.pack('<I',0x123456));u.reg_write(UC_X86_REG_EAX,LIST);u.reg_write(UC_X86_REG_ESI,1)
assert run(u,0x4fe2b9,{0x4fe2c3,0x4fe2e5})==0x4fe2c3
assert run(u,0x4fe652,{0x4fe658})==0x4fe658
# Cost display supports zero and four digits, independent of spell stock.
for cost in (0,1,255,9999):
 u=machine(cost=cost);u.reg_write(UC_X86_REG_ESI,LIST);u.reg_write(UC_X86_REG_ECX,26)
 assert run(u,0x4c8a52,{0x4c8a59})==0x4c8a59
 assert u.reg_read(UC_X86_REG_EDX)==cost
 assert u.reg_read(UC_X86_REG_ECX)==138
print('GF HP Casting: 336 actor/GF affordability cases, queued costs, rejection, live HP, Items and display passed')
# Save/load and dependency checks use a disposable project, never the active mod.
from tempfile import TemporaryDirectory
from plugins.ff8 import gameplay_settings as settings,paths
with TemporaryDirectory(prefix='lexeditor-gf-cost-save-') as tmp:
 root=Path(tmp);project=root/'project';settings.initialize_project(project)
 data=settings.load(project,paths.GAME_ROOT)
 data.update(gfHpCasting=True,singleGf=True,noMagicConsumption=True,gfHpCastingCosts=[0]*57)
 data['gfHpCastingCosts'][1]=321
 settings.save(data,paths.GAME_ROOT,project,runtime_root=root/'runtime',install_runtime=False)
 loaded=settings.load(project,paths.GAME_ROOT)
 assert loaded['gfHpCastingCosts'][1]==321 and loaded['gfHpCasting']
 assert casting.build_hext(True,data['gfHpCastingCosts']) in settings.patch_path(project).read_text()
 for missing in ('singleGf','noMagicConsumption'):
  invalid=dict(data);invalid[missing]=False;before=settings.settings_path(project).read_bytes()
  try:settings.save(invalid,paths.GAME_ROOT,project,runtime_root=root/'runtime',install_runtime=False)
  except ValueError as error:assert 'requires Monogamy and No Magic Consumption' in str(error)
  else:raise AssertionError('missing dependency accepted')
  assert settings.settings_path(project).read_bytes()==before
 data['gfHpCasting']=False
 settings.save(data,paths.GAME_ROOT,project,runtime_root=root/'runtime',install_runtime=False)
 assert settings.load(project,paths.GAME_ROOT)['gfHpCastingCosts'][1]==321
 assert 'GF HP Casting:' not in settings.patch_path(project).read_text()
for value in (-1,10000,1.5,True):
 invalid=[0]*57;invalid[1]=value
 try:casting.costs(invalid)
 except ValueError:pass
 else:raise AssertionError('invalid cost accepted')
print('Cost persistence, disabling, dependency rejection and numeric validation passed')
