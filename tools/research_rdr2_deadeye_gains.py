"""Map Dead Eye refill candidates to local script callers; this is not runtime proof."""
import argparse
import hashlib
import json
from pathlib import Path
import re

CANDIDATES = {
    '0x5A498FCA232F71E1': 'general multiplier setter',
    '0xAB3773E7AA1E9DCC': 'general multiplier getter',
    '0x51345AE20F22C261': 'restore by amount',
    '0x2498035289B5688F': 'restore outer ring',
    '0x4D1699543B1C023C': 'unknown special ability setting',
    '0xFA437FA0738C370C': 'unknown special ability operation',
}
FUNCTION = re.compile(r'^\w[\w *]*\s+(func_\d+)\(')
HASH = re.compile('|'.join(CANDIDATES))


def inspect(root):
    data_path=root/'_downloads/natives.json'
    natives=json.loads(data_path.read_text(encoding='utf-8'))['PLAYER']
    scripts=root/'_downloads/RDR2-Decompiled-Scripts/script_rel'
    if not scripts.is_dir(): raise FileNotFoundError(scripts)
    counts={key:0 for key in CANDIDATES}; examples={key:[] for key in CANDIDATES}
    files=0
    for path in sorted(scripts.glob('*.c')):
        files+=1; function=None
        with path.open(encoding='utf-8',errors='replace') as source:
            for line_number,line in enumerate(source,1):
                match=FUNCTION.match(line)
                if match: function=match.group(1)
                for match in HASH.finditer(line):
                    key=match.group();counts[key]+=1
                    if len(examples[key])<12:
                        examples[key].append({'script':path.name,'line':line_number,'function':function})
    return {'status':'research-only; kill-source suppression remains unproved','scriptsScanned':files,
            'nativeInputSha256':hashlib.sha256(data_path.read_bytes()).hexdigest(),
            'candidates':[{ 'hash':key,'role':role,'name':natives[key]['name'],
                           'callSites':counts[key],'examples':examples[key]}
                          for key,role in CANDIDATES.items()]}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime',type=Path,default=Path('C:/RDR2Mod'))
    parser.add_argument('--output',type=Path)
    args=parser.parse_args();result=inspect(args.runtime)
    text=json.dumps(result,indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(text+'\n',encoding='utf-8')
    print(f"Scanned {result['scriptsScanned']} scripts; research only, no kill suppression proven")
    for row in result['candidates']: print(f"{row['hash']} {row['name']}: {row['callSites']} calls")


if __name__=='__main__':main()
