"""Native CI must not refer to retired checks or missing source files."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from ff8_native_workflow import WORKFLOW


def test_native_workflow_python_entrypoints_exist():
    scripts = re.findall(r'\bpython editor/(\S+\.py)', WORKFLOW)
    modules = re.findall(r'\btests\.ff8\.\w+', WORKFLOW)
    assert scripts and modules, 'No native verification entrypoints discovered'
    references = scripts + [module.replace('.', '/') + '.py' for module in modules]
    missing = [name for name in references if not (ROOT / name).is_file()]
    assert not missing, f'Native build calls missing editor entrypoints: {missing}'


def test_native_workflow_triggers_exist():
    paths = re.findall(r"^      - '([^']+)'$", WORKFLOW, re.MULTILINE)
    assert paths, 'No native pull-request paths discovered'
    missing = [name for name in paths if not (ROOT / name.removesuffix('/**')).exists()]
    assert not missing, f'Native build watches missing editor paths: {missing}'
