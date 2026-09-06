"""PC LGP and field/world encounter editing, preserving all unrelated members.

Layout facts: Ficedula's LGP description; FF7 Field/Encounter and WorldMap
Encounters reverse-engineering documentation. No archive is extracted to disk.
"""
from __future__ import annotations
from collections import Counter
import struct
from .battle import number, read_values, write_values, validate_rows
from .format_codec import bounds, read_int, lzs_decode, lzs_encode


class LGP:
    def __init__(self, data: bytes):
        if not data.startswith(b'\0\0SQUARESOFT') or not data.endswith(b'FINAL FANTASY 7'):
            raise ValueError('Not a complete PC SQUARESOFT LGP archive')
        self.original=data;self.entries=[];self.changes={}
        count=read_int(data,12,4)
        if not 1<=count<=65535: raise ValueError('LGP member count is invalid')
        table_end=16+count*27
        bounds(data,16,count*27+3602)
        for i in range(count):
            at=16+i*27;name_raw=data[at:at+20]
            name=name_raw.split(b'\0',1)[0].decode('ascii')
            if not name or any(c in name for c in '/\\\0'):
                raise ValueError('LGP member has an invalid flat name')
            start=read_int(data,at+20,4)
            if start<table_end+3602: raise ValueError('LGP member overlaps its index')
            bounds(data,start,24)
            size=read_int(data,start+20,4);bounds(data,start+24,size)
            if start+24+size>len(data)-14: raise ValueError('LGP member overlaps its terminator')
            self.entries.append((name,start,size))
        # Exact aliases are permitted, partial data overlaps are not.
        spans=sorted(set((start,start+24+size) for _,start,size in self.entries))
        if any(a[1]>b[0] for a,b in zip(spans,spans[1:])):
            raise ValueError('LGP members overlap')

    def member(self,index):
        _,at,size=self.entries[index]
        return self.changes.get(index,self.original[at+24:at+24+size])

    def to_bytes(self):
        if not self.changes:return self.original
        result=bytearray(self.original[:-14])
        refs=Counter(at for _,at,_ in self.entries)
        for index,raw in sorted(self.changes.items()):
            name,old,size=self.entries[index]
            if raw==self.original[old+24:old+24+size]:continue
            if len(raw)==size and refs[old]==1:
                result[old+24:old+24+size]=raw
            else:
                at=len(result)
                if at+24+len(raw)>0xFFFFFFFF: raise ValueError('LGP exceeds 32-bit archive size')
                # Appending a replacement is supported by the original LGP format.
                # The lookup/conflict tables and all unmodified bytes stay intact.
                result.extend(self.original[old:old+20])
                result.extend(struct.pack('<I',len(raw)));result.extend(raw)
                struct.pack_into('<I',result,16+index*27+20,at)
        result.extend(b'FINAL FANTASY 7')
        return bytes(result)


def encounter_fields(count):
    fields=[number('enabled','Encounters enabled (0 or 1)',0,maximum=1),
            number('rate','Encounter rate (lower means more frequent)',1)]
    kinds=['Normal '+str(i+1) for i in range(6)]+['Back attack 1','Back attack 2','Side attack','Pincer attack']
    kinds += ['Chocobo '+str(i+1) for i in range(max(0,count-10))]
    for i,label in enumerate(kinds):
        fields += [number(f'battle{i}',label+' battle ID',2+2*i,2,maximum=1023,group='Battle selection'),
                   number(f'chance{i}',label+' weight (out of 64)',2+2*i,2,maximum=63,group='Battle selection')]
    return fields


FIELD_FIELDS=encounter_fields(10)
WORLD_FIELDS=encounter_fields(14)
YUFFIE_FIELDS=[number('level','Cloud level threshold',0,2,maximum=99),number('battle','Battle ID',2,2,maximum=1023)]
CHOCOBO_FIELDS=[number('battle','Battle ID',0,2,maximum=1023),number('rating','Chocobo rating (1 wonderful – 8 terrible)',2,2,maximum=8)]


def read_encounter(raw,count):
    bounds(raw,0,2+2*count)
    values={'enabled':raw[0],'rate':raw[1]}
    for i in range(count):
        value=read_int(raw,2+i*2)
        values.update({f'battle{i}':value&1023,f'chance{i}':value>>10})
    return values


def write_encounter(raw,values,count):
    fields=FIELD_FIELDS if count==10 else WORLD_FIELDS
    if not isinstance(values,dict) or set(values)!={f['key'] for f in fields}:raise ValueError('Invalid encounter field set')
    if any(type(value) is not int for value in values.values()):raise ValueError('Encounter values must be integers, not booleans')
    before=read_encounter(raw,count)
    if values==before:return raw  # Keep unusual original tables unchanged.
    for f in fields:
        v=values[f['key']]
        if type(v) is not int or not f['minimum']<=v<=f['maximum']:
            raise ValueError(f"{f['label']} is outside its storage range")
    if values['enabled'] and not values['rate']:raise ValueError('Enabled encounters require a nonzero rate (zero divides by zero in game)')
    if values['enabled'] and any(values[f'chance{i}']!=before[f'chance{i}'] for i in range(6)) and sum(values[f'chance{i}'] for i in range(6))!=64:
        raise ValueError('The six normal encounter weights must total 64')
    out=bytearray(raw);out[0:2]=bytes((values['enabled'],values['rate']))
    for i in range(count):struct.pack_into('<H',out,2+i*2,(values[f'chance{i}']<<10)|values[f'battle{i}'])
    return bytes(out)


def field_encounter_offset(raw):
    if raw[:2]!=b'\0\0' or read_int(raw,2,4)!=9:raise ValueError('Expected a nine-section PC field')
    pointers=list(struct.unpack_from('<9I',raw,6))
    if pointers!=sorted(set(pointers)) or pointers[0]<42:raise ValueError('Invalid field section pointers')
    for i,start in enumerate(pointers):
        size=read_int(raw,start,4);bounds(raw,start+4,size)
        if i<8 and start+4+size>pointers[i+1]:raise ValueError('Overlapping field sections')
    start=pointers[6]
    if read_int(raw,start,4)!=48:raise ValueError('Field encounter section must contain two 24-byte tables')
    return start+4


class FieldArchive:
    def __init__(self,data):
        self.lgp=LGP(data);self.fields={};self.errors={}
        for index,(name,_,_) in enumerate(self.lgp.entries):
            if name.casefold()=='maplist':continue
            try:
                raw=lzs_decode(self.lgp.member(index));offset=field_encounter_offset(raw)
                self.fields[index]=(raw,offset)
            except (ValueError,struct.error,UnicodeError) as error:
                self.errors[name]=str(error)
        if not self.fields:raise ValueError('No readable PC field encounter tables in flevel.lgp')

    def records(self,category='fieldEncounters'):
        return [{'id':index*2+table,'name':f'{self.lgp.entries[index][0]} / table {table}',
                 'description':'Six normal and four special battles. Field scripts select table 0/1. Only these tables change; scripts, dialogue and graphics are preserved.',
                 'values':read_encounter(raw[offset+table*24:offset+(table+1)*24],10)}
                for index,(raw,offset) in self.fields.items() for table in range(2)]

    def apply(self,category,rows):
        validate_rows(rows,self.records());pending={}
        for row in rows:
            index,table=divmod(row['id'],2);raw,at=self.fields[index];at+=table*24
            edited=write_encounter(raw[at:at+24],row.get('values'),10)
            if edited!=raw[at:at+24]:
                pending.setdefault(index,bytearray(raw))[at:at+24]=edited
        for index,raw in pending.items():
            self.lgp.changes[index]=lzs_encode(bytes(raw))
            self.fields[index]=(bytes(raw),self.fields[index][1])

    def to_bytes(self):return self.lgp.to_bytes()


class WorldArchive:
    def __init__(self,data):
        self.lgp=LGP(data)
        matches=[i for i,(name,_,_) in enumerate(self.lgp.entries) if name.casefold()=='enc_w.bin']
        if len(matches)!=1:raise ValueError('Expected one enc_w.bin world encounter member')
        self.index=matches[0];self.data=bytearray(self.lgp.member(self.index))
        if len(self.data)!=0x8A0:raise ValueError('enc_w.bin must contain 2208 bytes')

    def records(self,category):
        if category=='worldEncounters':
            return [{'id':i,'name':f'Region {i//4+1} / terrain set {i%4}',
                     'description':'Terrain set assignment is stored in the executable. Includes normal, special and Chocobo battles.',
                     'values':read_encounter(self.data[0xA0+i*32:0xC0+i*32],14)} for i in range(64)]
        count,start,fields=(8,0,YUFFIE_FIELDS) if category=='yuffieEncounters' else (32,32,CHOCOBO_FIELDS)
        return [{'id':i,'name':f'{"Yuffie threshold" if start==0 else "Chocobo rating"} {i}',
                 'description':'World map special encounter mapping.',
                 'values':read_values(self.data[start+i*4:start+i*4+4],fields)} for i in range(count)]

    def apply(self,category,rows):
        validate_rows(rows,self.records(category));out=bytearray(self.data)
        for row in rows:
            i=row['id']
            if category=='worldEncounters':
                at=0xA0+i*32;out[at:at+32]=write_encounter(self.data[at:at+32],row.get('values'),14)
            else:
                start,fields=(0,YUFFIE_FIELDS) if category=='yuffieEncounters' else (32,CHOCOBO_FIELDS)
                at=start+i*4
                values=row.get('values')
                if not isinstance(values,dict) or set(values)!={f['key'] for f in fields} or any(type(v) is not int for v in values.values()):
                    raise ValueError('Special encounters require an exact integer field set')
                if values!=read_values(self.data[at:at+4],fields):
                    out[at:at+4]=write_values(self.data[at:at+4],fields,row.get('values'))
        self.data=out

    def to_bytes(self):
        self.lgp.changes[self.index]=bytes(self.data)
        return self.lgp.to_bytes()
