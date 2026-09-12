"""Coordinate the prepared experiment; never launch the game or modify saves."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import catalog
import deploy

def closed():
    result=subprocess.check_output(['tasklist','/FI','IMAGENAME eq RDR2.exe','/FO','CSV','/NH'],text=True)
    if '"rdr2.exe"' in result.lower():raise RuntimeError('Close RDR2 before changing experiment files')

def catalog_action(action,target,bundle):
    before=sys.argv
    try:
        sys.argv=['catalog.py',action,'--catalog',str(target),'--bundle',str(bundle)]
        catalog.main()
    finally:sys.argv=before

def restore(game,bundle):
    """Attempt every independent recovery, even if an earlier recovery fails."""
    errors=[];manifest=json.loads((bundle/'manifest.json').read_text());target=Path(manifest['target'])
    if (bundle/'probe-install.json').exists():
        try:deploy.change('restore',game,bundle)
        except Exception as error:errors.append('probe: '+str(error))
    try:
        current=catalog.digest(target.read_bytes())
        if current==manifest['candidate']:catalog_action('restore',target,bundle)
        elif current!=manifest['before']:raise ValueError('Catalog changed; original retained at '+str(bundle/'original'))
    except Exception as error:errors.append('catalog: '+str(error))
    if (bundle/'isolation.json').exists():
        try:deploy.isolate('restore-mods',game,bundle)
        except Exception as error:errors.append('mods: '+str(error))
    if errors:raise RuntimeError('Recovery incomplete. Keep '+str(bundle)+'. '+ '; '.join(errors))
    (bundle/'active.json').unlink(missing_ok=True)
    return 'Original catalog and ASIs restored. The recovery bundle is retained.'

def activate(game,bundle,asi):
    marker=bundle/'active.json'
    if marker.exists() or (bundle/'disabled-asi').exists() or (bundle/'isolation.json').exists() or (bundle/'probe-install.json').exists():
        raise RuntimeError('Experiment already active or recovery pending. Run Restore first.')
    manifest=json.loads((bundle/'manifest.json').read_text());target=Path(manifest['target'])
    if catalog.digest(target.read_bytes())!=manifest['before']:raise ValueError('Catalog changed since preparation; activation stopped')
    if not asi or not asi.is_file():raise ValueError('Prepared probe is missing')
    if not manifest.get('probe_sha256') or deploy.digest(asi.read_bytes())!=manifest['probe_sha256']:
        raise ValueError('Prepared probe changed; activation stopped before changing files')
    try:
        deploy.isolate('isolate',game,bundle)
        catalog_action('install',target,bundle)
        deploy.change('install',game,bundle,asi)
        marker.write_text(json.dumps({'game':str(game.resolve()),'probe':deploy.digest(asi.read_bytes())}))
    except Exception as error:
        try:restore(game,bundle)
        except Exception as recovery:raise RuntimeError(f'Activation failed: {error}. {recovery}') from error
        raise RuntimeError(f'Activation failed: {error}. Original files were restored.') from error
    return 'Experiment activated. Start Story Mode and follow the prepared test sheet.'

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['activate','restore']);p.add_argument('--game',type=Path,required=True);p.add_argument('--bundle',type=Path,required=True);p.add_argument('--asi',type=Path);a=p.parse_args()
    closed()
    print(activate(a.game,a.bundle,a.asi) if a.action=='activate' else restore(a.game,a.bundle))
if __name__=='__main__':main()
