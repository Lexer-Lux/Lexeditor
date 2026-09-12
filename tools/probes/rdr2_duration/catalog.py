"""Bounded duration-category experiment. Generated game data stays outside source."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET

ITEMS=('CONSUMABLE_MEDICINE','CONSUMABLE_POTENT_MEDICINE','CONSUMABLE_SPECIAL_MEDICINE_CRAFTED','CONSUMABLE_TONIC','CONSUMABLE_POTENT_TONIC','CONSUMABLE_SPECIAL_TONIC_CRAFTED','CONSUMABLE_SNAKE_OIL','CONSUMABLE_POTENT_SNAKE_OIL')
CASES=[{'item':item,'category':category,'time':time,'units':units,'behavior':behavior} for item,(category,time,units,behavior) in zip(ITEMS,[(1,3,2,'HEALTH'),(2,3,2,'HEALTH'),(3,3,2,'HEALTH'),(4,3,2,'HEALTH'),(1,9,2,'HEALTH'),(1,3,1,'HEALTH'),(1,3,2,'STAMINA'),(4,9,2,'HEALTH')])]

def digest(data): return hashlib.sha256(data).hexdigest()
def joaat(value):
    h=0
    for c in value.lower().encode():
        h=(h+c)&0xffffffff;h=(h+(h<<10))&0xffffffff;h^=h>>6
    h=(h+(h<<3))&0xffffffff;h^=h>>11
    return (h+(h<<15))&0xffffffff

def item_span(text,key):
    matches=list(re.finditer(r'<item\s+key="'+re.escape(key)+r'"\s*>',text))
    if len(matches)!=1: raise ValueError('Expected one item: '+key)
    start=matches[0].start();depth=0
    for tag in re.finditer(r'</?item\b[^>]*>',text[start:]):
        token=tag.group()
        depth+= -1 if token.startswith('</') else (0 if token.endswith('/>') else 1)
        if depth==0:return start,start+tag.end()
    raise ValueError('Unclosed item '+key)

def prepare(text):
    root=ET.fromstring(text);effects=root.find('effectsids')
    if effects is None:raise ValueError('Missing effectsids')
    known={e.findtext('id') for e in effects}
    records=[]
    for i,case in enumerate(CASES):
        key=f'0x{joaat("LEX_DURATION_PROBE_"+str(i+1)):08X}'
        if any(e.findtext('key')==key for e in effects):raise ValueError('Probe already present')
        behavior='EFFECT_'+case['behavior']+'_OVERPOWERED'
        if behavior not in known:raise ValueError('Unknown behavior '+behavior)
        a,b=item_span(text,case['item']);segment=text[a:b]
        if len(re.findall(r'<effectids(?:\s*/)?\s*>',segment))!=1:raise ValueError('Missing effect list')
        segment=re.sub(r'<effectids\s*/>|<effectids>.*?</effectids>',f'<effectids><item><key>{key}</key></item></effectids>',segment,flags=re.S)
        text=text[:a]+segment+text[b:]
        records.append(f'<item><key>{key}</key><id>{behavior}</id><value value="0"/><percent value="0.00000000"/><time value="{case["time"]}"/><timeunits value="{case["units"]}"/><durationcategory>EFFECT_DURATION_CATEGORY_{case["category"]}</durationcategory></item>')
    if text.count('</effectsids>')!=1:raise ValueError('Ambiguous effectsids')
    text=text.replace('</effectsids>','\n'.join(records)+'\n</effectsids>')
    ET.fromstring(text)
    return text

def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','install','restore']);parser.add_argument('--catalog',type=Path,required=True);parser.add_argument('--bundle',type=Path,required=True)
    args=parser.parse_args();bundle=args.bundle;catalog=args.catalog
    if args.action=='prepare':
        if bundle.exists():raise ValueError('Bundle exists; preserve or restore it first')
        data=catalog.read_bytes()
        if shutil.disk_usage(bundle.parent).free < len(data)*3+10_000_000:raise ValueError('Not enough space for candidate and recovery')
        candidate=prepare(data.decode('utf-8-sig')).encode('utf-8')
        if data.startswith(b'\xef\xbb\xbf'):candidate=b'\xef\xbb\xbf'+candidate
        bundle.mkdir()
        try:
            (bundle/'original').write_bytes(data);(bundle/'catalog_sp.ymt').write_bytes(candidate)
            (bundle/'manifest.json').write_text(json.dumps({'target':str(catalog.resolve()),'before':digest(data),'candidate':digest(candidate),'cases':CASES},indent=2))
        except Exception:
            shutil.rmtree(bundle);raise
        print('Prepared bytes:',len(data)+len(candidate))
    else:
        manifest=json.loads((bundle/'manifest.json').read_text())
        if str(catalog.resolve())!=manifest['target']:raise ValueError('Wrong target')
        source=bundle/('catalog_sp.ymt' if args.action=='install' else 'original')
        expected=manifest['before' if args.action=='install' else 'candidate']
        if digest(catalog.read_bytes())!=expected:raise ValueError('Target changed; stop to preserve newer edits')
        data=source.read_bytes()
        if digest(data)!=manifest['candidate' if args.action=='install' else 'before']:raise ValueError('Bundle checksum failed')
        stage=catalog.with_name(catalog.name+'.duration-probe-stage')
        owned=False
        try:
            with stage.open('xb') as handle:
                owned=True;handle.write(data)
            stage.replace(catalog)
        finally:
            if owned:stage.unlink(missing_ok=True)
        print(args.action,'complete; bundle retained at',bundle)

if __name__=='__main__':main()
