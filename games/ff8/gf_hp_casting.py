"""Per-spell GF HP costs and guarded battle-only casting patches."""
from . import gf_hp_casting_asm as layout
from .gf_hp_casting_code import CODE
SPELL_COUNT=57
MAX_COST=9999
HOOKS=(
 (0x4C8A22,bytes.fromhex('F6 46 04 02 74 02 33 DB'),layout.ROW),
 (0x4C8A52,bytes.fromhex('0F BE 56 01 83 C1 70'),layout.NUMBER),
 (0x4FE2B9,bytes.fromhex('3B F5 7E 28 F6 40 04 02 75 22'),layout.SELECT),
 (0x4FE652,bytes.fromhex('8B 74 24 1C 33 D2'),layout.COMMIT),
)
def costs(values=None):
    if values is None:return [0]*SPELL_COUNT
    if not isinstance(values,list) or len(values)!=SPELL_COUNT:
        raise ValueError('GF HP costs must contain one value for each of the 57 spells')
    if any(type(v) is not int or not 0<=v<=MAX_COST for v in values):
        raise ValueError('GF HP costs must be whole numbers from 0 to 9,999')
    return list(values)
def verify_executable(stream):
    for address,original,_ in HOOKS:
        stream.seek(address-0x400000)
        if stream.read(len(original))!=original:raise RuntimeError(f'GF HP Casting: unsupported code at {address:X}')
    stream.seek(0x4C8A4A-0x400000)
    if stream.read(4)!=bytes.fromhex('85 DB 74 22'):raise RuntimeError('GF HP Casting: unsupported cost display')
def build_hext(enabled,values=None):
    values=costs(values)
    if not enabled:return ''
    rows=['# GF HP Casting: battle Magic spends GF HP; requires Monogamy and No Magic Consumption.']
    for address,data in CODE.items():
        rows.extend((f'{address:X}:{len(data):X}',f'{address:X} = {data.hex(" ").upper()}'))
    data=b''.join(v.to_bytes(2,'little') for v in values)
    rows.extend((f'{layout.COSTS:X}:{len(data):X}',f'{layout.COSTS:X} = {data.hex(" ").upper()}'))
    for address,original,target in HOOKS:
        data=b'\xE9'+(target-address-5).to_bytes(4,'little',signed=True)+b'\x90'*(len(original)-5)
        rows.append(f'{address:X} = {data.hex(" ").upper()}')
    rows.append('4C8A4A = 90 90 90 90')
    return '\n'.join(rows)+'\n'
