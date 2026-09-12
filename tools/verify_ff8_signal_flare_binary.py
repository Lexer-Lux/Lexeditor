"""Run linked Signal Flare validators against the supported EXE in an emulator."""
from pathlib import Path
import argparse
import struct
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/"_scratch/gf-spellbooks-test-deps"))

def verify(driver,exe):
    import capstone,pefile
    from unicorn import Uc,UC_ARCH_X86,UC_MODE_32
    from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_EAX,UC_X86_REG_EIP
    from games.ff8.ffnx_issue_51 import runtime_package
    runtime_package.verify_game_installation(exe.parent)
    pe=pefile.PE(str(driver));base=pe.OPTIONAL_HEADER.ImageBase;image=pe.get_memory_mapped_image()
    assert pe.FILE_HEADER.Machine==0x14c
    exports={e.name.decode():base+e.address for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
    def address(suffix):return next(value for name,value in exports.items() if name.endswith(suffix))
    for suffix in ('flare_definition_validate','flare_shop_validate','flare_menu_exit_validate',
                   'flare_use_world','flare_use_field','flare_shop_buy_guard','flare_shop_sell_guard',
                   'flare_transaction_allowed','flare_field_input_available'):
        address(suffix)
    assert b'Signal Flare enabled: item 199, all shops, 200 Gil;' in image
    assert bytes.fromhex('5767656c5f6a204a6a5f706300') in image
    decoder=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32);decoder.detail=True
    entry=address('flare_definition_validate')
    wrapper=list(decoder.disasm(image[entry-base:entry-base+32],entry))
    prepare=next(i.operands[0].imm for i in wrapper if i.mnemonic=='call')
    instructions=list(decoder.disasm(image[prepare-base:prepare-base+128],prepare))
    # Recover the linked globals from the explicit version preflight, rather
    # than pinning addresses that change at each link. Version 6 is US Nvidia.
    ff8_global=next(i.operands[0].mem.disp for i in instructions if i.mnemonic=='cmp' and
        i.operands[0].type==capstone.CS_OP_MEM and i.operands[0].size==4 and
        i.operands[1].type==capstone.CS_OP_IMM and i.operands[1].imm==0)
    version_global=None
    for first,second in zip(instructions,instructions[1:]):
        if (first.mnemonic=='mov' and len(first.operands)==2 and first.operands[1].type==capstone.CS_OP_MEM and
            second.mnemonic=='cmp' and second.op_str=='eax, 5'):
            version_global=first.operands[1].mem.disp;break
    assert version_global
    u=Uc(UC_ARCH_X86,UC_MODE_32)
    u.mem_map(base,(len(image)+4095)&~4095);u.mem_write(base,image)
    native=pefile.PE(str(exe)).get_memory_mapped_image()
    u.mem_map(0x400000,0x3000000);u.mem_write(0x400000,native)
    u.mem_write(ff8_global,struct.pack('<I',1));u.mem_write(version_global,struct.pack('<I',6))
    def call(suffix):
        u.mem_write(0x3100000,struct.pack('<I',0x3200000));u.reg_write(UC_X86_REG_ESP,0x3100000)
        u.emu_start(address(suffix),0x3200000,count=100000)
        assert u.reg_read(UC_X86_REG_EIP)==0x3200000
        return u.reg_read(UC_X86_REG_EAX)
    for suffix,site in [('flare_definition_validate',0x4a1c8e),('flare_shop_validate',0x4ebd55),('flare_menu_exit_validate',0x4c0b4b)]:
        assert call(suffix)==1,suffix
        old=bytes(u.mem_read(site,1));u.mem_write(site,bytes([old[0]^1]))
        assert call(suffix)==0,suffix
        u.mem_write(site,old)
    print('PASS linked Signal Flare: exports, name, activation marker; three actual DLL preflights and three instruction mutations.')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--driver',type=Path,required=True);parser.add_argument('--exe',type=Path,required=True)
    args=parser.parse_args();verify(args.driver,args.exe)
