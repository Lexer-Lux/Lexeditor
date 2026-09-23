"""Bounded FF7 battle AI assembler and fixed-size owner pools.

Format facts: ff7-flat-wiki Battle_Scenes/Battle_Script and Scarlet AIContainer.
Addresses in JMP/JZ/JNE are relative to the individual script, not its owner.
No executable Python/JavaScript is evaluated; assembly is game data only.
"""
from __future__ import annotations

import json
import re
import struct
from .format_codec import bounds, decode_text, encode_text, read_int

EVENTS = ('Initialize', 'Main', 'General counter', 'Death counter',
          'Physical counter', 'Magical counter', 'Battle end', 'Pre-action',
          *(f'Custom event {i}' for i in range(1, 9)))
OPS = {**{i: (f'LOAD{suffix}', 2) for i, suffix in enumerate(('BIT','8','16','24'))},
       **{16+i: (f'ADDR{suffix}', 2) for i, suffix in enumerate(('BIT','8','16','24'))}}
for first, names in ((0x30,'ADD SUB MUL DIV MOD AND OR NOT'), (0x40,'EQ NE GE LE GT LT'),
                     (0x50,'LAND LOR LNOT'), (0x73,'END POP LINK'),
                     (0x80,'MASK RANDOM RANDOMBIT COUNT MAX MIN MPCOST BIT'),
                     (0x90,'STORE DROP ACTION'), (0x94,'COPY GLOBAL ELEMENT')):
    OPS.update({first+i: (name,0) for i,name in enumerate(names.split())})
OPS.update({0x60:('PUSH8',1),0x61:('PUSH16',2),0x62:('PUSH24',3),
            0x70:('JZ',2),0x71:('JNE',2),0x72:('JMP',2),
            0x93:('MESSAGE',-1),0xA0:('DEBUG',-2),0xA1:('POP2',0),0x20:('NOP',0)})
BY_NAME = {v[0]: (k,v[1]) for k,v in OPS.items()}
JUMPS = {0x70, 0x71, 0x72}
LABEL = re.compile(r'[A-Za-z_][A-Za-z0-9_]*\Z')


def instructions(raw: bytes):
    """Decode through END, retaining opaque trailing bytes in the containing pool."""
    result, pos = [], 0
    while pos < len(raw):
        start, op = pos, raw[pos]
        name, size = OPS.get(op, (f'OP_{op:02X}', 0))
        pos += 1
        if size >= 0:
            bounds(raw, pos, size)
            arg = int.from_bytes(raw[pos:pos+size], 'little') if size else None
            pos += size
        elif size == -1:
            end = raw.find(b'\xff', pos)
            if end < 0: raise ValueError('AI MESSAGE has no FF terminator')
            arg = decode_text(raw[pos:end+1]); pos = end+1
        else:
            bounds(raw,pos,1)
            count=raw[pos]; pos+=1
            end=raw.find(b'\0',pos)
            if end < 0: raise ValueError('AI DEBUG has no NUL terminator')
            arg=(count,raw[pos:end].decode('ascii')); pos=end+1
        result.append((start,op,name,arg,pos))
        if op == 0x73: return result, pos
    raise ValueError('AI script has no END instruction')


def disassemble(raw: bytes) -> str:
    code, _ = instructions(raw)
    starts = {row[0] for row in code}
    targets = {arg for _,op,_,arg,_ in code if op in JUMPS}
    if not targets <= starts:
        raise ValueError('AI jump targets the middle of an instruction or leaves the script')
    lines=[]
    for at,op,name,arg,_ in code:
        if at in targets: lines.append(f'L{at:04X}:')
        if op in JUMPS: operand=f' L{arg:04X}'
        elif op == 0x93: operand=' '+json.dumps(arg,ensure_ascii=False)
        elif op == 0xA0: operand=f' {arg[0]} '+json.dumps(arg[1])
        elif arg is not None: operand=f' 0x{arg:X}'
        else: operand=''
        lines.append(name+operand)
    return '\n'.join(lines)


def assemble(source: str) -> bytes:
    if type(source) is not str or len(source)>65535:
        raise ValueError('AI assembly must be text of at most 65535 characters')
    out, labels, fixups = bytearray(), {}, []
    for line_no,line in enumerate(source.splitlines(),1):
        line=line.strip()
        if not line or line.startswith(';'): continue
        try:
            if line.endswith(':'):
                label=line[:-1]
                if not LABEL.fullmatch(label) or label in labels: raise ValueError('Invalid or duplicate label')
                labels[label]=len(out); continue
            name, _, arg=line.partition(' '); name=name.upper(); arg=arg.strip()
            if name.startswith('OP_') and re.fullmatch('OP_[0-9A-F]{2}',name):
                op=int(name[3:],16)
                if op in OPS: raise ValueError('Use the documented mnemonic for this opcode')
                if op >> 4 in (0,1,3,4): raise ValueError('Unsupported opcode with undefined operand semantics')
                size=0
            elif name in BY_NAME: op,size=BY_NAME[name]
            else: raise ValueError(f'Unknown mnemonic {name}')
            out.append(op)
            if op in JUMPS and LABEL.fullmatch(arg):
                fixups.append((len(out),arg));out.extend(b'\0\0')
            elif size>0:
                value=int(arg,0)
                if not 0<=value<1<<(8*size): raise ValueError('Operand out of range')
                out.extend(value.to_bytes(size,'little'))
            elif size == -1:
                value=json.loads(arg)
                encoded=encode_text(value)
                if b'\xff' in encoded[:-1]: raise ValueError('AI MESSAGE cannot contain embedded FF bytes')
                out.extend(encoded)
            elif size == -2:
                count,_,value=arg.partition(' '); count=int(count,0)
                text=json.loads(value)
                if type(text) is not str or '\0' in text or not 0<=count<=255:
                    raise ValueError('Invalid DEBUG operands')
                out.append(count);out.extend(text.encode('ascii'));out.append(0)
            elif arg: raise ValueError('This instruction takes no operand')
        except (ValueError, TypeError, UnicodeError, OverflowError) as error:
            raise ValueError(f'AI line {line_no}: {error}') from error
    for at,label in fixups:
        if label not in labels: raise ValueError(f'Undefined AI label: {label}')
        if labels[label]>65535: raise ValueError('AI label exceeds 16-bit address space')
        struct.pack_into('<H',out,at,labels[label])
    if not out: return b''  # An empty editor removes that event.
    code,end=instructions(bytes(out))
    if end!=len(out): raise ValueError('Instructions after END are not executable; remove them')
    starts={row[0] for row in code}
    if any(arg not in starts for _,op,_,arg,_ in code if op in JUMPS):
        raise ValueError('AI jump must target an instruction inside this script')
    return bytes(out)


class Pool:
    """Preserve unrelated owners, gaps and padding; allocate only known free FF space.

Existing owner/script offsets are left alone for same-size or shorter edits.
Growing/new scripts are placed in trailing FF slack and the corresponding
pointer is updated. Old script bytes remain inactive, preserving opaque data.
Compaction is intentionally not implicit. Capacity errors leave the pool intact.
"""
    def __init__(self, raw: bytes, owners: int):
        self.raw=bytes(raw);self.owners=owners
        bounds(raw,0,owners*2)
        self.offsets=list(struct.unpack_from('<'+'H'*owners,raw))
        self.scripts={};self.spans={};self.tables={}
        occupied=owners*2
        for owner,offset in enumerate(self.offsets):
            if offset==65535: continue
            if offset<owners*2: raise ValueError('AI owner pointer overlaps its header')
            bounds(raw,offset,32);occupied=max(occupied,offset+32)
            ends=[p for p in self.offsets if offset<p<65535]
            owner_end=min(ends,default=len(raw))
            table=struct.unpack_from('<16H',raw,offset);self.tables[owner]=table
            for event,relative in enumerate(table):
                if relative==65535: continue
                start=offset+relative
                if relative<32 or start>=owner_end: raise ValueError('AI event pointer leaves its owner')
                end=min((offset+p for p in table if relative<p<65535),default=owner_end)
                code,used=instructions(raw[start:end]);script=raw[start:start+used]
                # Validate known jump boundaries before exposing an editable script.
                disassemble(script)
                self.scripts[owner,event]=script;self.spans[owner,event]=(start,start+used)
                occupied=max(occupied,start+used)
        # Unknown non-FF bytes anywhere are never taken as free space.
        last=next((i+1 for i in range(len(raw)-1,occupied-1,-1) if raw[i]!=255),occupied)
        self.free=(last+1)&~1

    def records(self, prefix: str, base_id=0):
        return [{'id':base_id+owner,'name':f'{prefix} {owner}',
                 'description':'Battle AI assembly. Empty event removes it. Labels relocate jumps; END is required. Capacity and byte structure are checked, not gameplay logic.',
                 'values':{f'script{i}':disassemble(self.scripts[owner,i]) if (owner,i) in self.scripts else '' for i in range(16)}}
                for owner in range(self.owners)]

    def apply(self, values_by_owner: dict[int,dict]) -> bytes:
        result=bytearray(self.raw);free=self.free
        # Build whole owner blocks only for owners whose scripts need extra space.
        # Keep within original owner's partition: growing an owner moves it to the
        # end and relocates all its event offsets together, never across owners.
        for owner,values in values_by_owner.items():
            if type(owner) is not int or not 0<=owner<self.owners or not isinstance(values,dict) or set(values)!={f'script{i}' for i in range(16)}:
                raise ValueError('Invalid AI owner or event field set')
            current={i:self.scripts.get((owner,i),b'') for i in range(16)}
            updated={i:(current[i] if values[f'script{i}']==(disassemble(current[i]) if current[i] else '') else assemble(values[f'script{i}'])) for i in range(16)}
            if updated==current: continue
            old=self.offsets[owner]
            aliased=old!=65535 and self.offsets.count(old)>1
            event_pointers=[p for p in self.tables.get(owner,()) if p!=65535]
            shared_events=len(set(event_pointers))!=len(event_pointers)
            fits=old!=65535 and not aliased and not shared_events and all(len(updated[i])<=len(current[i]) for i in range(16))
            if fits:
                for event,code in updated.items():
                    if code==current[event]:continue
                    if not code:struct.pack_into('<H',result,old+event*2,65535)
                    else:
                        start,_=self.spans[owner,event];result[start:start+len(code)]=code
                continue
            if not any(updated.values()):
                struct.pack_into('<H',result,owner*2,65535);continue
            block=bytearray(b'\xff'*32)
            for event,code in updated.items():
                if code:
                    struct.pack_into('<H',block,event*2,len(block));block.extend(code)
            block.extend(b'\xff'*(len(block)%2))
            if free+len(block)>len(result):raise ValueError('AI pool has insufficient trailing space for this edit; shorten scripts')
            struct.pack_into('<H',result,owner*2,free)
            result[free:free+len(block)]=block;free+=len(block)
        # Reparse to reject relocations that produce invalid owner boundaries.
        Pool(bytes(result),self.owners)
        return bytes(result)


def metadata():
    return [{'key':f'script{i}','label':name,'dataType':'text','group':'AI scripts','language':'ff7-asm'} for i,name in enumerate(EVENTS)]
