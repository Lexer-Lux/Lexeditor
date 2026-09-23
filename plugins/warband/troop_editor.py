"""Edit troop record fields without importing or executing Module System code."""
from __future__ import annotations
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading

FIELDS = ('id','name','plural','flags','scene','reserved','faction','inventory','attributes','proficiencies','skills','face1','face2','image')
_LOCK = threading.Lock()


def _source(path):
    raw = path.read_bytes()
    for encoding in ('utf-8','cp1254','latin1'):
        try:return raw.decode(encoding),encoding,raw
        except UnicodeDecodeError:pass


_TROOP_START = re.compile(r'(?m)^[ \t]*(#*)[ \t]*\[\s*["\'][^"\']+["\']\s*,\s*["\']')


def _top_level_troop_starts(text):
    """Return only literal/cut troop entries directly inside troops = [...]."""
    from .server import _skip_python_string
    assignment = re.search(r'(?m)^[ \t]*troops[ \t]*=[ \t]*\[', text)
    if not assignment:
        return [], len(text)
    outer = text.find('[', assignment.start(), assignment.end())
    depth = 1
    cursor = outer + 1
    outer_end = len(text)
    while cursor < len(text):
        char = text[cursor]
        if char in '"\'':
            cursor = _skip_python_string(text, cursor)
            continue
        if char == '#':
            newline = text.find('\n', cursor)
            cursor = len(text) if newline < 0 else newline + 1
            continue
        if char == '[':
            depth += 1
        elif char == ']':
            depth -= 1
            if depth == 0:
                outer_end = cursor + 1
                break
        cursor += 1

    candidates = [match for match in _TROOP_START.finditer(text)
                  if outer < match.start() < outer_end]
    depths = {}
    depth = 1
    cursor = outer + 1
    for match in candidates:
        target = match.start()
        while cursor < target:
            char = text[cursor]
            if char in '"\'':
                cursor = _skip_python_string(text, cursor)
                continue
            if char == '#':
                newline = text.find('\n', cursor, target)
                cursor = target if newline < 0 else newline + 1
                continue
            if char == '[':
                depth += 1
            elif char == ']':
                depth -= 1
            cursor += 1
        depths[target] = depth

    accepted = []
    skip_until = -1
    for match in candidates:
        if depths.get(match.start()) != 1 or match.start() < skip_until:
            continue
        accepted.append(match)
        block = text[match.start():outer_end]
        cut = bool(match[1])
        normalized = re.sub(r'(?m)^([ \t]*)#+',
                            lambda marker: ' ' * len(marker[0]), block) if cut else block
        record_start = normalized.find('[')
        record_depth = 0
        cursor = record_start
        while 0 <= cursor < len(normalized):
            char = normalized[cursor]
            if char in '"\'':
                cursor = _skip_python_string(normalized, cursor)
                continue
            if char == '#':
                newline = normalized.find('\n', cursor)
                cursor = len(normalized) if newline < 0 else newline + 1
                continue
            if char == '[':
                record_depth += 1
            elif char == ']':
                record_depth -= 1
                if record_depth == 0:
                    skip_until = match.start() + cursor + 1
                    break
            cursor += 1
    return accepted, outer_end


def _records(text):
    from .server import _skip_python_string, _split_item_fields
    starts, outer_end = _top_level_troop_starts(text)
    rows=[]
    for record_index, match in enumerate(starts):
        stop=starts[record_index+1].start() if record_index+1<len(starts) else outer_end
        block=text[match.start():stop]
        cut=bool(match[1])
        normalized=re.sub(r'(?m)^([ \t]*)#+',lambda m:' '*len(m[0]),block) if cut else block
        start=normalized.index('[');cursor=start;depth=0
        while cursor<len(normalized):
            char=normalized[cursor]
            if char in '"\'':
                cursor=_skip_python_string(normalized,cursor);continue
            if char=='#':
                cursor=normalized.find('\n',cursor)
                if cursor<0:break
                continue
            if char=='[':depth+=1
            elif char==']':
                depth-=1
                if depth==0:break
            cursor+=1
        if depth:
            names=re.match(r"\[\s*[\"']([^\"']+)[\"']\s*,\s*[\"']([^\"']*)[\"']",normalized[start:])
            rows.append({'recordIndex':record_index,'id':names[1],'name':names[2],'plural':'','status':'CUT' if cut else 'active',
                         'line':text.count('\n',0,match.start())+1,'fields':{},'_spans':[],
                         'problem':'This source record has unbalanced brackets. Repair its source before editing.'})
            continue
        spans=_split_item_fields(normalized,start,cursor+1)
        if len(spans)<11:continue
        expressions=[normalized[a:b] for a,b in spans]
        values=dict(zip(FIELDS,expressions))
        for key in ('id','name','plural'):
            values[key]=ast.literal_eval(values[key])
        rows.append({'recordIndex':record_index,'id':values['id'],'name':values['name'],'plural':values['plural'],
                     'status':'CUT' if cut else 'active','line':text.count('\n',0,match.start())+1,
                     'fields':values,'_spans':[(a+match.start(),b+match.start()) for a,b in spans]})
    return rows

def _number(expression,symbols):
    node=ast.parse(re.sub(r'(?<=[0-9a-fA-F])L\b','',expression),mode='eval').body
    def value(n):
        if isinstance(n,ast.Constant) and type(n.value) is int:return n.value
        if isinstance(n,ast.Name):return symbols[n.id]
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.Invert):return ~value(n.operand)
        if isinstance(n,ast.BinOp):
            a,b=value(n.left),value(n.right)
            if isinstance(n.op,ast.BitOr):return a|b
            if isinstance(n.op,ast.BitAnd):return a&b
            if isinstance(n.op,ast.LShift) and 0<=b<=256:return a<<b
            if isinstance(n.op,ast.Add):return a+b
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='level' and len(n.args)==1:
            return value(n.args[0])<<32
        raise ValueError('This source expression cannot be reduced to a fixed number')
    return value(node)


def _symbols(root):
    symbols={};pending=[]
    for filename in ('header_common.py','header_troops.py','module_troops.py'):
        path=root/filename
        if path.exists():
            pending+=re.findall(r'(?m)^([A-Za-z_]\w*)\s*=\s*([^\n#]+)',_source(path)[0])
    for _ in range(8):
        for key,expr in pending:
            if key in symbols:continue
            try:symbols[key]=_number(expr.strip(),symbols)
            except (KeyError,ValueError,SyntaxError,TypeError):pass
    return symbols


def troop_data(root):
    root=Path(root);path=root/'module_troops.py'
    if not path.exists():return {'rows':[],'sha256':'','factions':[],'items':[],'flags':{}}
    text,_,raw=_source(path);symbols=_symbols(root)
    rows=_records(text)
    for row in rows:
        row.pop('_spans')
        if row.get('problem'):
            row.update(faction='',flags='',items=[],stats={},level='',flagValue=None);continue
        row['faction']=row['fields']['faction'];row['flags']=row['fields']['flags']
        row['items']=re.findall(r'\bitm_\w+',row['fields']['inventory'])
        row['stats']={}
        try:
            number=_number(row['fields']['attributes'],symbols)
            row['stats']={name:(number>>shift)&255 for name,shift in [('strength',0),('agility',8),('intelligence',16),('charisma',24),('level',32)]}
        except (KeyError,ValueError,SyntaxError):pass
        row['level']=row['stats'].get('level','')
        try:row['flagValue']=_number(row['flags'],symbols)
        except (KeyError,ValueError,SyntaxError):row['flagValue']=None
    def ids(filename,prefix):
        file=root/filename
        return re.findall(r'(?m)^('+prefix+r'\w+)\s*=',_source(file)[0]) if file.exists() else []
    return {'rows':rows,'sha256':hashlib.sha256(raw).hexdigest(),
            'factions':ids('ID_factions.py','fac_'),'items':ids('ID_items.py','itm_'),
            'flags':{k:v for k,v in symbols.items() if k.startswith('tf_') and v>0 and v&(v-1)==0 and v>15},
            'types':{k:v for k,v in symbols.items() if k.startswith('tf_') and 0<=v<16}}


def save_troops(root,expected,edits):
    root=Path(root);path=root/'module_troops.py'
    with _LOCK:
        text,encoding,raw=_source(path)
        if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('Troop source changed; reload before saving')
        records=_records(text);by_index={r['recordIndex']:r for r in records};patches=[];edited=set()
        for edit in edits:
            if 'recordIndex' in edit:
                record_index=int(edit['recordIndex']);row=by_index.get(record_index)
                if row is None:raise ValueError('Troop record no longer exists')
                original=str(edit.get('originalId',edit.get('id','')))
                if original and row['id']!=original:
                    raise ValueError(f"Troop record {record_index} changed from {original} to {row['id']}; reload before saving")
            else:
                troop_id=str(edit.get('id',''));matches=[r for r in records if r['id']==troop_id]
                if len(matches)!=1:
                    raise ValueError(f"Troop ID {troop_id!r} is missing or ambiguous; reload and use record identity")
                row=matches[0];record_index=row['recordIndex']
            if record_index in edited:raise ValueError('Send each troop record only once')
            edited.add(record_index)
            for field,val in edit['fields'].items():
                if field=='id' or field not in row['fields']:raise ValueError('Unknown or fixed troop field')
                if field in ('name','plural'):replacement=json.dumps(str(val),ensure_ascii=False)
                else:
                    replacement=str(val).strip()
                    if '\n' in replacement or '\r' in replacement or '#' in replacement:raise ValueError('Use a single source expression')
                    ast.parse(replacement,mode='eval')
                a,b=row['_spans'][FIELDS.index(field)];patches.append((a,b,replacement))
        candidate=text
        for a,b,value in sorted(patches,reverse=True):candidate=candidate[:a]+value+candidate[b:]
        if [(r['id'],len(r['_spans'])) for r in _records(candidate)]!=[(r['id'],len(r['_spans'])) for r in records]:raise ValueError('Save changed troop identities or field count')
        if any(ord(char)>127 for char in candidate) and not re.search(r'coding[:=]\s*[-\w.]+', '\n'.join(candidate.splitlines()[:2])):
            candidate=f"# coding: {encoding}\n"+candidate
        encoded=candidate.encode(encoding)
        python27=Path(r'C:\Python27\python.exe')
        with tempfile.TemporaryDirectory(prefix='warband-troop-check-') as temp:
            probe=Path(temp)/'module_troops.py';probe.write_bytes(encoded)
            if python27.exists():
                result=subprocess.run([str(python27),'-c',"import sys; compile(open(sys.argv[1],'rb').read(),sys.argv[1],'exec')",str(probe)],capture_output=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                if result.returncode:raise ValueError(result.stderr.decode('utf-8',errors='replace'))
        if not patches:return {'saved':0}
        if path.read_bytes()!=raw:raise ValueError('Troop source changed while validating; reload before saving')
        backup=path.with_suffix('.py.lexeditor.bak');backup.write_bytes(raw)
        fd,tmp=tempfile.mkstemp(prefix='.troops-',dir=root)
        try:
            with os.fdopen(fd,'wb') as stream:stream.write(encoded)
            os.replace(tmp,path)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
        return {'saved':len(edited),'sha256':hashlib.sha256(encoded).hexdigest(),'backup':str(backup)}
