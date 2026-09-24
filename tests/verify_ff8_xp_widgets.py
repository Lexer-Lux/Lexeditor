"""Check native XP widget call sites and level-row coordinates without running FF8."""
import hashlib,struct
from pathlib import Path
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_EIP,UC_X86_REG_EAX
exe=Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe")
data=exe.read_bytes()
assert hashlib.sha256(data).hexdigest()=="064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570"
image=pefile.PE(data=data).get_memory_mapped_image()
for target,calls in {0x4C0780:[0x4C08F4,0x4CB66C,0x4CC846,0x4F6E8E,0x4F6F17,0x4F7361,0x4F73EE],0x4C1D50:[0x4C1ADA],0x4C1ED0:[0x4C1AC2],0x4C2090:[0x4C1AED],0x4D3E40:[0x4D3DB5],0x4D41B0:[0x4D3D34,0x4D3D4A]}.items():
 for call in calls:
  assert image[call-0x400000]==0xe8
  assert call+5+struct.unpack_from('<i',image,call-0x400000+1)[0]==target

def widget(address,args,setup=None):
 u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0,0x3000000);u.mem_write(0x400000,image)
 stack=0x2900000;stop=0x2800000
 if setup: setup(u)
 u.mem_write(stack,struct.pack('<'+'I'*(len(args)+1),stop,*args));u.reg_write(UC_X86_REG_ESP,stack)
 calls=[]
 def hook(u,pc,size,user):
  code=bytes(u.mem_read(pc,size))
  if code[0]==0xe8:
   target=pc+5+struct.unpack_from('<i',code,1)[0]
   sp=u.reg_read(UC_X86_REG_ESP)
   calls.append((target,struct.unpack('<7I',u.mem_read(sp,28))))
   u.reg_write(UC_X86_REG_EAX,0);u.reg_write(UC_X86_REG_EIP,pc+size)
 u.hook_add(UC_HOOK_CODE,hook)
 u.emu_start(address,stop,count=10000)
 assert u.reg_read(UC_X86_REG_EIP)==stop
 return calls
for x,y in [(0,0),(31,19),(140,72)]:
 calls=widget(0x4C0780,[1,2,x,y,0x1CFE0E8,0x1D771B0,0])
 number=next(args for target,args in calls if target==0x4A3530)
 assert number[2]==((y+75)<<16)|(x+141)
 text=[args for target,args in calls if target==0x4BDE30]
 assert any(args[2:4]==(x+79,y+75) for args in text)
 calls=widget(0x4D3E40,[1,2,x,y,3,10])
 level=next(args for target,args in calls if target==0x49F850)
 assert level[2:4]==(x+10,y+52)
 calls=widget(0x4D41B0,[0x2000000,1,2,x,y,3])
 level=next(args for target,args in calls if target==0x4BF330)
 assert level[3:5]==(x+79,y+75),level

def menu_state(u):
 u.mem_write(0x2000035,bytes([0,1,2,3,4,255,255,255,255,255,255]))
 for slot in range(8):
  u.mem_write(0x1D771B0+32*slot+8,struct.pack('<HHBB',635,1000,11+slot,30))

for address,spacing in [(0x4C1D50,26),(0x4C1ED0,52)]:
 for slot in range(3):
  calls=widget(address,[0x2000000,1,2,slot],menu_state)
  level=next(args for target,args in calls if target==0x4B77C0 and args[2]==0x145)
  assert level[3:5]==(114,46+spacing*slot),level
calls=widget(0x4C2090,[0x2000000,1,2],menu_state)
levels=[args[3:5] for target,args in calls if target==0x4B77C0 and args[2]==0x145]
assert levels==[(44,129),(164,129)],levels
for selector,label in [(1,0x142),(0,0x146)]:
 calls=widget(0x4BF020,[0x2000000,1,2,20,30,3660,selector])
 native_label=next(args for target,args in calls if target==0x4B77C0)
 assert native_label[2:5]==(label,20,30),native_label
print("PASS: 13 native call sites; shared character and GF list level coordinates at three offsets")
print("PASS: active and reserve main-menu LV positions from native widgets")
print("PASS: native playtime and countdown clock label selectors")
