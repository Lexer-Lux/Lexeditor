"""Read installed FF7 data and round-trip it only into a disposable project.

No deployment, game launch, installed-file writes, or automatic uploads.
Native gameplay and the user's listening judgement are separate acceptance.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from datetime import datetime, timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from games.ff7 import datasets, extended
from games.ff7.kernel import resolve_kernel


def sha256(path):
    result=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):result.update(chunk)
    return result.hexdigest().upper()


def check_installation(game:Path):
    game=game.resolve();report={'game':str(game),'datasets':{},'errors':{},'installedFilesUnchanged':False,
        'scope':'Read and disposable project save/readback only; not deployment, gameplay or a listening test.'}
    sources={}
    try:
        sources['kernel']=resolve_kernel(game)[0]
    except (OSError,ValueError) as error:report['errors']['kernel']=str(error)
    for family in extended.FAMILIES:
        try:sources[family]=extended.resolve_source(game,family)[0]
        except (OSError,ValueError) as error:report['errors'][family]=str(error)
    before={str(path):sha256(path) for path in sources.values()}
    with tempfile.TemporaryDirectory(prefix='lexeditor-ff7-readback-') as temporary:
        project=Path(temporary)/'project'
        kernel=datasets.load_datasets(game,project)
        report['errors'].update(kernel['errors'])
        if kernel['records']:
            try:
                datasets.save_datasets(game,project,kernel)
                restored=datasets.load_datasets(game,project)
                for key,rows in kernel['records'].items():
                    if rows!=restored['records'].get(key):raise ValueError(f'{key}: project readback differs')
                    report['datasets'][key]={'records':len(rows),'readback':'passed'}
            except Exception as error:report['errors']['kernelSave']=str(error)
        other=extended.load_extended(game,project);report['errors'].update(other['errors'])
        for family,metadata in other['families'].items():
            records={key:other['records'][key] for key in metadata['categories'] if key in other['records']}
            if not records:continue
            try:
                result=extended.save_extended(game,project,dict(metadata,family=family,records=records))
                for key,rows in records.items():
                    if rows!=result['records'][key]:raise ValueError(f'{key}: project readback differs')
                    report['datasets'][key]={'records':len(rows),'readback':'passed'}
                if metadata.get('memberErrors'):report['errors'][family+'Members']=metadata['memberErrors']
            except Exception as error:report['errors'][family+'Save']=str(error)
    report['installedFilesUnchanged']=all(Path(path).is_file() and sha256(Path(path))==value for path,value in before.items())
    if not report['installedFilesUnchanged']:report['errors']['sourceIntegrity']='An installed file changed during the check. No installed file was intentionally written.'
    report['passed']=bool(report['datasets']) and not report['errors'] and report['installedFilesUnchanged']
    return report


def discover():
    from games.ff7.plugin import PLUGIN as current
    from games.ff7_2013.plugin import PLUGIN as legacy
    roots=[]
    saved=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'Lexeditor/game-installations.json'
    try:
        games=json.loads(saved.read_text(encoding='utf-8')).get('games',{})
        roots += [Path(games[key]['root']) for key in ('ff7','ff7-2013') if games.get(key,{}).get('root')]
    except (OSError,ValueError,TypeError):pass
    for plugin in (current,legacy):
        spec=plugin.installation
        if os.environ.get(spec.root_env):roots.append(Path(os.environ[spec.root_env]))
        roots.extend(spec.default_roots)
    return sorted({root.resolve() for root in roots if root.is_dir()},key=str)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game',type=Path,action='append',help='Installed game root; repeat for both editions. Otherwise use saved/default locations.')
    parser.add_argument('--report',type=Path,help='JSON report outside game directories.')
    args=parser.parse_args();roots=args.game or discover()
    if not roots:parser.error('No FF7 installation found. Supply --game "path to the installed game".')
    target=args.report or Path(tempfile.gettempdir())/('Lexeditor-ff7-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')+'.json')
    if any(target.resolve().is_relative_to(root.resolve()) for root in roots):parser.error('The report must be outside all installed game directories.')
    reports=[check_installation(root) for root in roots]
    target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent,prefix=target.name+'.',suffix='.tmp',mode='w',encoding='utf-8',delete=False) as stream:
        temp=Path(stream.name);json.dump(reports,stream,indent=2,ensure_ascii=False)
    try:os.replace(temp,target)
    finally:temp.unlink(missing_ok=True)
    for report in reports:print(f"{report['game']}: {len(report['datasets'])} readable datasets; {len(report['errors'])} problems; sources unchanged: {report['installedFilesUnchanged']}")
    print('Report:',target)
    return 0 if all(report['passed'] for report in reports) else 1

if __name__=='__main__':raise SystemExit(main())
