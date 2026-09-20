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

def widget(address,args):
 u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0,0x3000000);u.mem_write(0x400000,image)
 stack=0x2900000;stop=0x2800000
 u.mem_write(stack,struct.pack('<'+'I'*(len(args)+1),stop,*args));u.reg_write(UC_X86_REG_ESP,stack)
 calls=[]
 call_pcs=[]
 def hook(u,pc,size,user):
  code=bytes(u.mem_read(pc,size))
  if code[0]==0xe8:
   target=pc+5+struct.unpack_from('<i',code,1)[0]
   sp=u.reg_read(UC_X86_REG_ESP)
   calls.append((target,struct.unpack('<7I',u.mem_read(sp,28))))
   call_pcs.append((pc,target))
   u.reg_write(UC_X86_REG_EAX,0);u.reg_write(UC_X86_REG_EIP,pc+size)
 u.hook_add(UC_HOOK_CODE,hook)
 u.emu_start(address,stop,count=10000)
 assert u.reg_read(UC_X86_REG_EIP)==stop
 return calls,call_pcs
for x,y in [(0,0),(31,19),(140,72)]:
 calls,pcs=widget(0x4C0780,[1,2,x,y,0x1CFE0E8,0x1D771B0,0])
 numbers=[(pc,args) for (target,args),(pc,pc_target) in zip(calls,pcs)
          if target==0x4A3530 and pc_target==0x4A3530 and args[2]==((y+75)<<16)|(x+141)]
 assert len(numbers)==1, numbers
 text=[args for target,args in calls if target==0x4BDE30]
 assert any(args[2:4]==(x+79,y+75) for args in text)
 calls,_=widget(0x4D3E40,[1,2,x,y,3,10])
 level=next(args for target,args in calls if target==0x49F850)
 assert level[2:4]==(x+10,y+52)
 calls,_=widget(0x4D41B0,[0x2000000,1,2,x,y,3])
 level=next(args for target,args in calls if target==0x4BF330)
 assert level[3:5]==(x+79,y+75),level
print("PASS: 13 native call sites; shared character and GF list level coordinates at three offsets")
