"""Execute native SPR/SPD curves and Flying EVA accuracy without game writes."""
from pathlib import Path
import struct,sys,hashlib
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
try: import unicorn
except ImportError: sys.path.insert(0,str(ROOT/'_scratch/gf-spellbooks-test-deps'))
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32
from unicorn.x86_const import *
import pefile
from games.ff8 import character_growth as growth, flying_eva
exe=Path(r'D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe').read_bytes()
assert hashlib.sha256(exe).hexdigest()=='064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570'
image=pefile.PE(data=exe).get_memory_mapped_image();STACK=0x2908000;STOP=0x2800000

def machine():
 u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0x400000,0x2600000);u.mem_write(0x400000,image);return u

def call(u,level,char,stat):
 u.reg_write(UC_X86_REG_ESP,STACK);u.mem_write(STACK,struct.pack('<IIII',STOP,level,char,stat));u.emu_start(0x496440,STOP,count=2000);return u.reg_read(UC_X86_REG_EAX)
u=machine();u.mem_write(0x1CFE0F0,b'\0');u.mem_write(0x1CF7604,bytes([0,1,0,1]))
assert call(u,16,0,4)==0xffffffe4 # -28, later stored as 228
assert image[growth.HOOK-0x400000:growth.HOOK-0x400000+6]==growth.ORIGINAL
u.mem_write(growth.CAVE,growth.build_payload());u.mem_write(growth.HOOK,b'\xE9'+struct.pack('<i',growth.CAVE-growth.HOOK-5)+b'\x90')
u.ctl_remove_cache(growth.HOOK,growth.HOOK+6)
for char in range(11):
 u.mem_write(0x1CFE0F0+152*char,bytes([char]))
 u.mem_write(0x1CF7604+36*char,bytes([0,255,0,255,0,1,0,1]))
 for level in range(1,101):
  assert call(u,level,char,4)==0,(char,level,'SPR',call(u,level,char,4))
  assert call(u,level,char,5)==0,(char,level,'SPD')
# Permanent SPR bonus must survive the zero base.
u.mem_write(0x1CFE0F5,b'\x17');assert call(u,16,0,4)==23
# Every standard stat floors negative base before bonuses, but preserves
# positive native results. Check against an unpatched machine for positive data.
vanilla=machine()
for stat in range(1,5):
 address=0x1CF75F8+4*(stat-1)
 bonus=0x1CFE0F2+stat-1
 u.mem_write(bonus,b'\0')
 u.mem_write(address,bytes([0,1,0,1]))
 for level in range(1,101): assert call(u,level,0,stat)==0
 u.mem_write(bonus,b'\x17'); assert call(u,16,0,stat)==23
 u.mem_write(bonus,b'\0')
 u.mem_write(address,bytes([12,5,100,100]))
 vanilla.mem_write(address,bytes([12,5,100,100]))
 for level in range(1,101): assert call(u,level,0,stat)==call(vanilla,level,0,stat)
# Actual native accuracy tail after the classifier, before RNG. Full 255 hit
# no longer swallows a 100-point penalty. Exceptions retain ordinary value.
for flying,melee,floating,hit,bonus,expected in [(1,1,0,255,100,0),(1,1,0,255,25,191),(1,1,0,90,25,165),(0,1,0,255,100,650),(1,0,0,255,100,650),(1,1,1,255,100,650)]:
 v=machine();v.reg_write(UC_X86_REG_ESP,STACK);v.reg_write(UC_X86_REG_EAX,0);v.reg_write(UC_X86_REG_ECX,0);v.reg_write(UC_X86_REG_ESI,0);v.reg_write(UC_X86_REG_EBP,0x270)
 v.mem_write(0x1D27B10+0x270,struct.pack('<I',0x2700000));v.mem_write(0x2700000,struct.pack('<I',0x2710000));v.mem_write(0x27100F7,bytes([2*flying]))
 v.mem_write(0x1D27B8C,struct.pack('<I',0x100*melee));v.mem_write(0x1D27B18,struct.pack('<I',0x2000*floating));v.mem_write(0x1D2A238,bytes([hit]));v.mem_write(0x1D27BD2+0x270,b'\0')
 v.mem_write(flying_eva.CAVE,flying_eva.build_payload(bonus));v.emu_start(flying_eva.CAVE,0x492F29,count=100)
 assert v.reg_read(UC_X86_REG_EDI)==expected,(flying,melee,floating,hit,bonus,v.reg_read(UC_X86_REG_EDI))
print('Native SPR/SPD zero across 11 characters x100 levels; bonus preservation; Flying EVA255 and exceptions passed')

# Run the actual browser curve function, not a Python copy.
import subprocess, shutil
editor=(ROOT/'games/ff8/editor.html').read_text(encoding='utf-8')
curve=editor[editor.index('  const characterCurveOrder='):editor.index('  function characterCurveFormula(')]
js=curve+"""
const fields=(stat,values)=>values.map((value,i)=>({field:stat.toLowerCase()+'_'+(i+1),value}));
if(characterCurveValue('STR',fields('STR',[0,1,0,1]),16)!==0)throw Error('standard lower guard missing');
if(characterCurveValue('VIT',fields('VIT',[0,1,0,1]),16,true)!==-28)throw Error('raw base lost');
for(let level=1;level<=100;level++){
 if(characterCurveValue('SPR',fields('SPR',[0,255,0,255]),level)!==0)throw Error('SPR not zero');
 if(characterCurveValue('SPD',fields('SPD',[0,1,0,1]),level)!==0)throw Error('SPD not zero');
}
"""
node=shutil.which('node') or r'C:\Users\Lexer\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
subprocess.run([node,'-e',js],check=True)
assert 'range:{min:axisMin,max:axisMax}' in editor
print('Browser curve execution matches zero patch and exposes negative unpatched growth')
