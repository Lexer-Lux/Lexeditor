"""Install/remove only this probe binary, with identity checks and bounded recovery."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

def digest(data):return hashlib.sha256(data).hexdigest()
def change(action,game,bundle,asi=None):
    target=game/'DurationProbe.asi';receipt=bundle/'probe-install.json'
    if action=='install':
        if receipt.exists() or target.exists():raise ValueError('Probe install already exists; restore it first')
        data=asi.read_bytes()
        manifest=bundle/'manifest.json'
        if manifest.exists() and digest(data)!=json.loads(manifest.read_text()).get('probe_sha256'):
            raise ValueError('Prepared probe changed; refusing installation')
        record={'target':str(target.resolve()),'sha256':digest(data)}
        stage=game/'DurationProbe.asi.staging'
        owned=False
        try:
            with stage.open('xb') as handle:
                owned=True
                if handle.write(data)!=len(data):raise OSError('Incomplete probe write')
            if digest(stage.read_bytes())!=record['sha256']:raise OSError('Probe staging checksum failed')
            with receipt.open('x') as handle:json.dump(record,handle)
            # Windows rename refuses to replace an existing destination.
            stage.rename(target)
        except Exception as error:
            raise RuntimeError('Probe installation failed; recovery bundle: '+str(bundle)) from error
        finally:
            if owned:stage.unlink(missing_ok=True)
    else:
        record=json.loads(receipt.read_text())
        if str(target.resolve())!=record['target']:raise ValueError('Wrong game directory')
        if target.exists():
            if digest(target.read_bytes())!=record['sha256']:raise ValueError('Probe binary changed; retained for inspection')
            target.unlink()
        receipt.unlink()

ISOLATE=('Banking.asi','CollectibleCalibrator.asi','GameplayTweaks.asi','Rampage.asi')
def isolate(action,game,bundle):
    receipt=bundle/'isolation.json';disabled=bundle/'disabled-asi'
    if action=='isolate':
        if receipt.exists() or disabled.exists():raise ValueError('Isolation already exists; restore it first')
        unknown=[p.name for p in game.glob('*.asi') if p.name not in (*ISOLATE,'vfs.asi','DurationProbe.asi')]
        if unknown:raise ValueError('Unreviewed ASIs: '+', '.join(unknown))
        records=[{'name':name,'sha256':digest((game/name).read_bytes())} for name in ISOLATE if (game/name).exists()]
        receipt.write_text(json.dumps({'game':str(game.resolve()),'files':records},indent=2))
        disabled.mkdir()
        for record in records:
            target=game/record['name']
            if digest(target.read_bytes())!=record['sha256']:raise ValueError('ASI changed during isolation')
            target.rename(disabled/record['name'])
    else:
        info=json.loads(receipt.read_text())
        if info['game']!=str(game.resolve()):raise ValueError('Wrong game directory')
        for record in info['files']:
            original=game/record['name'];saved=disabled/record['name']
            if saved.exists():
                if original.exists() or digest(saved.read_bytes())!=record['sha256']:raise ValueError('ASI changed; preserve recovery')
            elif not original.exists() or digest(original.read_bytes())!=record['sha256']:raise ValueError('Missing original ASI; preserve recovery')
        for record in info['files']:
            saved=disabled/record['name']
            if saved.exists():saved.rename(game/record['name'])
        if disabled.exists():disabled.rmdir()
        receipt.unlink()

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['install','restore','isolate','restore-mods']);p.add_argument('--game',type=Path,required=True);p.add_argument('--bundle',type=Path,required=True);p.add_argument('--asi',type=Path);a=p.parse_args()
    processes=subprocess.check_output(['tasklist','/FI','IMAGENAME eq RDR2.exe','/FO','CSV','/NH'],text=True)
    if '"rdr2.exe"' in processes.lower():raise RuntimeError('Close RDR2 before changing probe files')
    if a.action=='install' and not a.asi:p.error('--asi is required for install')
    if a.action in ('isolate','restore-mods'):isolate(a.action,a.game,a.bundle)
    else:change(a.action,a.game,a.bundle,a.asi)
if __name__=='__main__':main()
