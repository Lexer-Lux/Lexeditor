"""Conservative Build 42 fluid scalar editor.

The current schema exposes ColorReference and DisplayName at fluid block level;
child Properties/Categories/blend/poison blocks remain read-only and preserved.
"""
from __future__ import annotations

import os
from pathlib import Path
import re

from . import core

EDITABLE_FIELDS = ("ColorReference", "DisplayName")


def _blocks(text: str) -> list[tuple[core.Block, core.Block]]:
    masked = core._masked_code(text)
    pattern = re.compile(r"\bfluid\s+([^\s{]+(?:\s+[^\s{]+)*)\s*\{", re.IGNORECASE)
    result=[]
    for module in core._top_level_blocks(text, "module"):
        cursor=body_start=module.open_brace+1
        while cursor < module.close_brace:
            match=pattern.search(masked,cursor,module.close_brace)
            if not match: break
            depth=0
            for ch in masked[body_start:match.start()]:
                if ch=="{": depth+=1
                elif ch=="}": depth-=1
            if depth:
                cursor=match.end(); continue
            opened=masked.find("{",match.start(),match.end())
            closed=core._matching_brace(masked,opened,module.close_brace)
            result.append((module,core.Block("fluid",match.group(1).strip(),match.start(),opened,closed)))
            cursor=closed+1; body_start=cursor
    return result


def read(root: Path) -> dict:
    root=Path(root).resolve(); rows=[]; errors=[]
    for path in core.script_paths(root):
        data,text=core._read_utf8(path); relative=path.relative_to(root).as_posix()
        try: pairs=_blocks(text)
        except core.ProjectZomboidError as error:
            errors.append({"path":relative,"error":str(error)}); continue
        for module,block in pairs:
            values,duplicates=core._properties(text,block)
            rows.append({"key":f"{relative}:{module.name}.{block.name}","path":relative,"module":module.name,
                         "id":block.name,"fullType":f"{module.name}.{block.name}","sha256":core.sha256_bytes(data),
                         "fields":{key:values.get(key,"") for key in EDITABLE_FIELDS},
                         "duplicateKeys":sorted(set(duplicates)&set(EDITABLE_FIELDS))})
    return {"rows":rows,"errors":errors}


def save(root: Path, relative: str, module_name: str, fluid_id: str,
         expected_sha256: str, edits: dict) -> dict:
    root=Path(root).resolve(); path=core._safe_relative(root,relative)
    allowed={os.path.normcase(str(candidate.resolve())) for candidate in core.script_paths(root)}
    if os.path.normcase(str(path.resolve())) not in allowed:
        raise core.ProjectZomboidError("Script is outside supported Build 42 script roots")
    data,text=core._read_utf8(path)
    if core.sha256_bytes(data)!=expected_sha256:
        raise core.ProjectZomboidError("Script changed outside Lexeditor; reload before saving")
    if not isinstance(edits,dict) or not edits or set(edits)-set(EDITABLE_FIELDS):
        raise core.ProjectZomboidError("Save contains unsupported fluid fields")
    matches=[(module,block) for module,block in _blocks(text) if module.name==module_name and block.name==fluid_id]
    if len(matches)!=1: raise core.ProjectZomboidError("Fluid identity is missing or ambiguous")
    _,block=matches[0]; values,duplicates=core._properties(text,block)
    unsafe=set(duplicates)&set(edits)
    if unsafe: raise core.ProjectZomboidError("Cannot safely edit duplicated fluid properties: "+", ".join(sorted(unsafe)))
    missing=set(edits)-set(values)
    if missing: raise core.ProjectZomboidError("Writer changes existing properties only; missing: "+", ".join(sorted(missing)))
    validated={key:core._clean_scalar(value,key) for key,value in edits.items()}
    if any(any(ch in value for ch in ",{}") for value in validated.values()):
        raise core.ProjectZomboidError("Fluid scalar contains script punctuation")
    body_start=block.open_brace+1; body=text[body_start:block.close_brace]; masked=core._masked_code(body)
    replacements=[]; depth=0; last=0
    for match in core._PROPERTY_RE.finditer(body):
        for ch in masked[last:match.start()]:
            if ch=="{": depth+=1
            elif ch=="}": depth=max(0,depth-1)
        last=match.end(); key=match.group("key")
        if depth==0 and key in validated:
            replacements.append((body_start+match.start("value"),body_start+match.end("value"),validated[key]))
    if len(replacements)!=len(validated): raise core.ProjectZomboidError("Could not locate every fluid property safely")
    for start,end,value in sorted(replacements,reverse=True): text=text[:start]+value+text[end:]
    core._atomic_write(path,text.encode("utf-8"))
    return next(row for row in read(root)["rows"] if row["path"]==relative and row["module"]==module_name and row["id"]==fluid_id)
