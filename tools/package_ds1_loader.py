"""Build an author-side standalone loader package; never install into a game."""
from pathlib import Path
import argparse
import json
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from plugins.ds1 import runtime_package

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--plan',action='store_true')
parser.add_argument('--output',type=Path)
args = parser.parse_args()
if args.plan:
    print(json.dumps(runtime_package.plan(),indent=2))
elif args.output:
    print(runtime_package.package(args.output))
else:
    parser.error('Choose --plan or --output FOLDER')
