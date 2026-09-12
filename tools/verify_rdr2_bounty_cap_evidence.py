"""Verify both discovered bounty-cap layers; never claim runtime implementation."""
import argparse
import json
from pathlib import Path
import re


def function(source, name):
    match=re.search(r'(?m)^\w[\w *]*\s+'+re.escape(name)+r'\([^\n]*\)\s*\{',source)
    if not match: raise AssertionError(f'Missing {name}')
    depth=1;start=match.end();end=start
    while depth and end<len(source):
        depth+=(source[end]=='{')-(source[end]=='}');end+=1
    if depth: raise AssertionError(f'Incomplete {name}')
    return source[start:end-1]


def verify(source,natives):
    cap=function(source,'func_2107');apply=function(source,'func_790')
    assert natives['PLAYER']['0xEA6DE0CD15AECBE2']['name']=='_SET_MAX_WANTED_LEVEL_2'
    assert 'return 30000;' in cap and 'return 50000;' in cap and 'return 150000;' in cap
    assert 'iVar0 = func_2107();' in apply
    clamp=re.search(r'if\s*\(iParam1 > iVar0\)\s*\{\s*iParam1 = iVar0;',apply)
    assert clamp, 'Independent script clamp is absent'
    engine=apply.index('PLAYER::_SET_MAX_WANTED_LEVEL_2(iVar0);')
    bounty=apply.index('LAW::_SET_BOUNTY_FOR_PLAYER(PLAYER::PLAYER_ID(), iParam1);')
    saved=apply.index('Global_40.f_358[iParam0 /*12*/] = iParam1;')
    assert clamp.start()<engine<bounty<saved, 'Cap must precede live and persisted bounty writes'
    assert 'func_790(func_792(), LAW::_GET_BOUNTY_FOR_PLAYER(PLAYER::PLAYER_ID()));' in function(source,'func_174')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime',type=Path,default=Path('C:/RDR2Mod'))
    args=parser.parse_args()
    source=(args.runtime/'_downloads/RDR2-Decompiled-Scripts/script_rel/short_update.c').read_text(encoding='utf-8')
    natives=json.loads((args.runtime/'_downloads/natives.json').read_text(encoding='utf-8'))
    verify(source,natives)
    for before,after in [('if (iParam1 > iVar0)','if (iParam1 < iVar0)'),
                         ('PLAYER::_SET_MAX_WANTED_LEVEL_2(iVar0);','PLAYER::_SET_MAX_WANTED_LEVEL_2(5);'),
                         ('Global_40.f_358[iParam0 /*12*/] = iParam1;','Global_40.f_358[iParam0 /*12*/] = 0;')]:
        try: verify(source.replace(before,after),natives)
        except (AssertionError,ValueError): pass
        else: raise AssertionError('Evidence mutation was not detected: '+before)
    current=args.runtime/'_downloads/RDR2-Decompiled-Scripts-1491.50/1491.50/script_rel/short_update.ysc.c'
    if current.exists():
        import hashlib
        text=current.read_text(encoding='utf-8')
        assert hashlib.sha256(current.read_bytes()).hexdigest()=='216119d7dcb5455e3c4a9df49ed30388f42461aec7e26f705d8e975a0b62a298', 'Re-audit changed versioned decompilation'
        for name,offset in [('func_790','2494B'),('func_791','24A0B'),('func_2107','559A2'),('func_2108','559FC')]:
            assert re.search(r'\b'+name+r'\([^\n]*Position - 0x'+offset+r'\b',text), name
        assert 'if (hParam1 > maxWantedLevel)' in text
        assert 'LAW::SET_BOUNTY(PLAYER::PLAYER_ID(), hParam1);' in text
        print('1491.50 annotated source mapping: cap0x559A2..0x559FC; apply0x2494B..0x24A0B; installed bytes NOT verified')
    print('PASS: bounty cap native and independent script/persisted clamp identified;3 mutations rejected')
    print('NOT IMPLEMENTED: changing the native alone cannot raise the script-clamped regional maximum')


if __name__=='__main__':main()
