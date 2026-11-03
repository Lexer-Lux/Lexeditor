"""Entry point for the loader's private data merger, without the editor UI."""
from pathlib import Path
import runpy
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
runpy.run_module('plugins.ds1.standalone_runtime',run_name='__main__')
