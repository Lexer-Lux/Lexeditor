"""Project-only path checks and verified file replacement shared by FF7 writers."""
from pathlib import Path
import os
import tempfile


def target_path(game_root,project_root,source,relative):
    root,game=Path(project_root).resolve(),Path(game_root).resolve()
    target=Path(project_root)/relative
    if root==game or root.is_relative_to(game):
        raise ValueError('The project must not overwrite the installed KERNEL or other game data')
    resolved=target.resolve()
    if not resolved.is_relative_to(root) or resolved==game or resolved.is_relative_to(game) or target.is_symlink():
        raise ValueError('FF7 output escapes the project or aliases the installed game')
    if target.exists() and (not target.is_file() or target.samefile(source)):
        raise ValueError('FF7 project output aliases the source or is not a file')
    return target


def replace_project(target:Path,output:bytes,active:bytes,existed:bool,check):
    """Caller supplies final source/snapshot checks, executed after staging."""
    target.parent.mkdir(parents=True,exist_ok=True)
    temporary=None;backup=None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent,prefix=target.name+'.',suffix='.tmp',delete=False) as stream:
            temporary=Path(stream.name);stream.write(output);stream.flush();os.fsync(stream.fileno())
        if temporary.read_bytes()!=output:raise ValueError('FF7 temporary file failed readback')
        check()
        if target.exists()!=existed or (existed and target.read_bytes()!=active):
            raise ValueError('FF7 project changed while saving; reload before saving')
        if existed:
            with tempfile.NamedTemporaryFile(dir=target.parent,prefix=target.name+'.lexeditor-',suffix='.bak',delete=False) as stream:
                backup=stream.name;stream.write(active);stream.flush();os.fsync(stream.fileno())
        check()
        if target.exists()!=existed or (existed and target.read_bytes()!=active):
            raise ValueError('FF7 project changed while saving; reload before saving')
        os.replace(temporary,target)
        return backup
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)


def records_match(category,expected,actual):
    left={r['id']:r['values'] for r in expected};right={r['id']:r['values'] for r in actual}
    if left.keys()!=right.keys():return False
    if category not in {'characterAI','enemyAI','formationAI'}:return left==right
    from .ai import assemble
    for index,values in left.items():
        if not isinstance(values,dict) or values.keys()!=right[index].keys():return False
        for key,value in values.items():
            if value!=right[index][key] and assemble(value)!=assemble(right[index][key]):return False
    return True


def case_path(root, relative):
    """Resolve a Windows game-relative path without guessing between case aliases."""
    path=Path(root)
    for part in Path(relative).parts:
        if not path.is_dir():return None
        matches=[child for child in path.iterdir() if child.name.casefold()==part.casefold()]
        if len(matches)>1:raise ValueError(f'Ambiguous case-insensitive FF7 source: {relative}')
        if not matches:return None
        path=matches[0]
    return path if path.is_file() else None
