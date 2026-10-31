"""Terminate a synthetic runtime install without allowing exception rollback."""
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from plugins.ds1 import tweak_mods

game,library,phase,request = sys.argv[1:]
if Path(tempfile.gettempdir()).resolve() not in Path(game).resolve().parents:
    raise SystemExit('This worker only writes temporary test fixtures')
payload = json.loads(Path(request).read_bytes())
tweak_mods.ensure_game_closed = lambda:None  # Only this temporary fixture exists.
write = tweak_mods.atomic_write


def interrupted(path,data):
    write(path,data)
    if Path(path).name == phase:
        os._exit(37)


tweak_mods.atomic_write = interrupted
tweak_mods._write_runtime(Path(game),bytes.fromhex(payload['patch']),['New project'],payload['project'],library=Path(library))
raise SystemExit('The requested interruption phase was not reached')
