"""Export a built mod as a clean, prebuilt folder or ZIP for players."""
from pathlib import Path
import argparse
import shutil
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from plugins.ds1 import runtime_mods, exe_patches

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('mod',type=Path)
parser.add_argument('--game',required=True,type=Path)
parser.add_argument('--output',required=True,type=Path)
args = parser.parse_args()
vanilla = (args.game/exe_patches.EXECUTABLE).read_bytes()
if args.output.suffix.lower() == '.zip':
    if args.output.exists():
        parser.error('The release ZIP already exists')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='lex-ds1-release-') as temporary:
        folder = runtime_mods.write_release(args.mod,Path(temporary),vanilla,game_root=args.game)
        shutil.make_archive(str(args.output.with_suffix('')),'zip',folder.parent,folder.name)
else:
    print(runtime_mods.write_release(args.mod,args.output,vanilla,game_root=args.game))
