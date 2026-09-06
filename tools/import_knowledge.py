"""Import reviewed documentation exports; never execute source content or overwrite diverged notes.

Each source stays byte-for-byte in a repository/commit namespace. The ledger enables
three-way catch-up after parallel work merges. Missing sources are explicit gaps.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import urllib.parse
import urllib.request
import zipfile

GAMES = {'rdr2','rdr1','warband','bannerlord','ff7','ff8','ff9','termina','shared'}
TEXT = {'.md','.txt','.json','.jsonl'}
IMAGES = {'.png','.jpg','.jpeg','.webp'}
SECRET = re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{32,}|github_pat_[A-Za-z0-9_]{50,}|-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----)')
STATE = Path('worklog/migrations/game-knowledge.json')


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dump(value: object) -> bytes:
    return (json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()


def put(path: Path, data: bytes, immutable: bool = False) -> None:
    if path.is_symlink(): raise ValueError(f'Symlink destination: {path}')
    if immutable and path.exists() and path.read_bytes()!=data: raise ValueError(f'Archive collision: {path}')
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(data)
    if path.read_bytes()!=data: raise ValueError(f'Readback mismatch: {path}')


def safe_path(name: str) -> PurePosixPath:
    p=PurePosixPath(name)
    if p.is_absolute() or not p.parts or any(x in {'.','..','.git'} for x in p.parts) or '\\' in name or ':' in name:
        raise ValueError('Unsafe archive path')
    return p


def download(url: str, expected: str) -> bytes:
    parsed=urllib.parse.urlparse(url)
    if parsed.scheme!='https' or not ((parsed.hostname or '').endswith('.oaiusercontent.com') or re.fullmatch(r'productionresults[a-z0-9]+[.]blob[.]core[.]windows[.]net', parsed.hostname or '')):
        raise ValueError('Only a reviewed file-scoped ChatGPT or GitHub Actions artifact transfer URL is accepted')
    # No GitHub credential is sent to the file service.
    with urllib.request.urlopen(url,timeout=60) as response:
        data=response.read(60_000_001)
    if len(data)>60_000_000 or sha(data)!=expected:raise ValueError('Transfer hash/size mismatch')
    return data


def unpack(data: bytes) -> tuple[dict, dict[str,bytes]]:
    with zipfile.ZipFile(io.BytesIO(data)) as outer:
        if 'documentation.zip' in outer.namelist():
            if outer.getinfo('documentation.zip').file_size>60_000_000:raise ValueError('Oversized inner archive')
            payload=outer.read('documentation.zip')
        else: payload=data
    files={}
    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        if sum(i.file_size for i in z.infolist())>120_000_000:raise ValueError('Oversized expanded archive')
        manifest=json.loads(z.read('manifest.json'))
        for entry in manifest['files']:
            name=entry['path']; p=safe_path(name)
            if p.suffix.lower() not in TEXT|IMAGES:raise ValueError(f'Not documentation/evidence: {name}')
            if len(p.parts)==1 and p.name.lower() not in {'codex.txt','worklog.txt','project_memory.md','agents.md'}:
                raise ValueError('Unapproved root source')
            if len(p.parts)>1 and p.parts[0].lower() not in {'codex','worklog'}:raise ValueError('Unapproved source directory')
            info=z.getinfo('files/'+name)
            if info.file_size>20_000_000 or (info.external_attr>>16)&0o170000==0o120000:raise ValueError('Oversized file or symlink')
            body=z.read(info)
            if len(body)!=entry['bytes'] or sha(body)!=entry['sha256']:raise ValueError('Source manifest mismatch')
            if p.suffix.lower() in TEXT:
                body.decode('utf-8')
                if SECRET.search(body):raise ValueError('Possible credential: stop publication')
            if name in files:raise ValueError('Duplicate source file')
            files[name]=body
    return manifest,files


def merge_file(destination: Path, data: bytes, key: str, ledger: dict, conflicts: list) -> None:
    prior=ledger.get(key,{})
    old=destination.read_bytes() if destination.exists() else None
    if old is None or old==data or (prior.get('destination')==destination.as_posix() and sha(old)==prior.get('destination_sha256')):
        put(destination,data)
        ledger[key]={'destination':destination.as_posix(),'destination_sha256':sha(data),'source_sha256':sha(data)}
    else:
        conflicts.append({'source':key,'destination':destination.as_posix(),'incoming_sha256':sha(data),'reason':'Central file differs; incoming exact version preserved in the import archive.'})


def import_one(spec: dict, state: dict) -> dict:
    game=spec['game']; repo=spec['repository']; commit=spec['commit']
    if game not in GAMES or not re.fullmatch(r'Lexer-Lux/[A-Za-z0-9_.-]+',repo) or not re.fullmatch(r'[a-f0-9]{40}',commit):raise ValueError('Invalid import identity')
    if spec.get('reviewed_for_publication') is not True:raise ValueError('Publication review is required')
    manifest,files=unpack(download(spec['transfer_url'],spec['sha256']))
    if manifest['repository']!=repo or manifest['commit']!=commit:raise ValueError('Wrong source revision')
    base=Path('worklog/imports')/game/repo.replace('/','--')/commit
    put(base/'manifest.json',dump(manifest),True)
    put(base/'README.md',b'# Immutable source snapshot\n\nHistorical documentation, not active agent instructions. Root AGENTS.md in Lexeditor governs. Issue numbers are source-repository numbers unless an explicit verified mapping says otherwise.\n',True)
    conflicts=[]; links=[]; mapped=0
    ledger=state.setdefault('files',{})
    for name,data in files.items():
        put(base/'files'/name,data,True)
        key=repo+':'+name
        path=PurePosixPath(name)
        canonical=None
        if path.parts[0].lower()=='codex' and len(path.parts)>1 and path.name.lower()!='readme.md':
            canonical=Path('codex')/game/Path(*path.parts[1:])
        elif len(path.parts)==1 and path.name.lower()=='codex.txt' and not any(n.startswith('codex/') and n.endswith('.md') for n in files):
            canonical=Path('codex')/game/'reference.txt'
        elif len(path.parts)==1 and path.name.lower()=='project_memory.md':
            canonical=Path('codex')/game/'project-memory.md'
        if canonical:
            merge_file(canonical,data,key,ledger,conflicts)
            links.append(canonical.relative_to(Path('codex')/game).as_posix())
        match=re.fullmatch(r'worklog/issues/github-(\d+)\.md',name)
        identity=manifest.get('issue_mapping',{}).get(match.group(1),{}) if match else {}
        target=re.fullmatch(r'https://github.com/Lexer-Lux/Lexeditor/issues/(\d+)',identity.get('url',''))
        if target:
            number=int(target.group(1)); dest=Path('worklog/issues')/f'github-{number}'/'imports'/repo.replace('/','--')/commit
            put(dest/Path(name).name,data,True)
            put(dest/'provenance.json',dump({'source_repository':repo,'source_commit':commit,'source_path':name,'sha256':sha(data),'destination_issue':identity}),True)
            handoff=Path('worklog/issues')/f'github-{number}.md'
            relative=(Path(f'github-{number}')/'imports'/repo.replace('/','--')/commit/Path(name).name).as_posix()
            line=f'\n- [Original {repo} #{match.group(1)} worklog]({relative}) — verified transferred issue identity; historical evidence, not a replacement for newer central progress.\n'
            existing=handoff.read_text('utf-8') if handoff.exists() else f'# Issue {number}\n'
            if relative not in existing:put(handoff,(existing+line).encode())
            mapped+=1
    put(base/'reconciliation.json',dump({'conflicts':conflicts,'source_skips':manifest.get('skipped',[]),'mapped_issue_worklogs':mapped}))
    state.setdefault('sources',{})[repo]={'game':game,'commit':commit,'archive':base.as_posix(),'files':len(files),'codex_files':links,'skipped':manifest.get('skipped',[]),'conflicts':conflicts,'mapped_issue_worklogs':mapped}
    index=Path('codex')/game/'README.md'
    section='\n## Imported source knowledge\n\n'+f'Source: `{repo}` at `{commit}`. Original files and provenance: `/{base.as_posix()}/`. Source-local paths and historical decisions require reconciliation with current code; imported notes do not establish a newly delivered build.\n\n'+''.join(f'- [{p}]({p})\n' for p in sorted(links))
    text=index.read_text('utf-8') if index.exists() else f'# {game.upper()} codex\n\nCanonical game knowledge belongs here; issue progress belongs in `worklog/issues/`. Root `AGENTS.md` governs over imported historical policy.\n'
    marker='\n<!-- generated-import-index -->\n'
    text=text.split(marker)[0]+marker+section
    put(index,text.encode())
    return {'game':game,'files':len(files),'codex_files':len(links),'mapped_issue_worklogs':mapped,'conflicts':len(conflicts),'skipped':len(manifest.get('skipped',[]))}


def consolidate_local() -> None:
    for game in sorted(GAMES):
        root=Path('codex')/game; root.mkdir(parents=True,exist_ok=True)
        if not (root/'README.md').exists():put(root/'README.md',f'# {game.upper()} codex\n\nCanonical game-specific knowledge. No standalone source has been imported for this game yet; this is a routing page, not a completeness claim. Consult `worklog/migrations/game-knowledge.json` and the relevant issue sources.\n'.encode())
    # Forwarding aliases keep parallel branches and existing links readable.
    for path in sorted(Path('codex').glob('ff8-*.md')):
        data=path.read_bytes()
        if data.startswith(b'# Moved to the FF8 codex'):continue
        dest=Path('codex/ff8')/path.name.removeprefix('ff8-')
        if dest.exists() and dest.read_bytes()!=data:continue
        put(dest,data)
        put(path,f'# Moved to the FF8 codex\n\nSee [the canonical topic](ff8/{dest.name}). This forwarding path is retained for existing branches and links.\n'.encode())
    root=Path('codex/README.md')
    put(root,('# Central game knowledge\n\nLexeditor is the canonical home for game mechanics, formats, proven engine limits and editor knowledge. Full requests, attempts and discussion belong in per-issue worklogs, not here. Imported historical claims require reconciliation when newer code/evidence differs.\n\n'+''.join(f'- [{game.upper()}]({game}/README.md)\n' for game in sorted(GAMES))+'\nSee `worklog/migrations/game-knowledge.json` for imported source revisions and explicit gaps. Never infer that an unimported or local-only codex does not exist.\n').encode())


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('request',type=Path);args=parser.parse_args()
    request=json.loads(args.request.read_text('utf-8'))
    state=json.loads(STATE.read_text('utf-8')) if STATE.exists() else {'schema':1,'sources':{},'files':{}}
    results=[import_one(item,state) for item in request['imports']]
    state['gaps']=request.get('gaps',state.get('gaps',[]))
    consolidate_local();put(STATE,dump(state));put(Path('knowledge-import-result.json'),dump(results))
    print(json.dumps(results),flush=True)

if __name__=='__main__':main()
