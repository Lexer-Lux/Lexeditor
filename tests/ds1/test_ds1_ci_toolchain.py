"""Native fixtures find CI's pinned compiler without compiling on the workstation."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from plugins.ds1.runtime import build
from tools import check_plugin


def test_only_ds1_ci_installs_the_native_fixture_compiler():
    workflows = check_plugin.workflow_files()
    ds1 = workflows['ds1-checks.yml']
    install = 'python -m pip install ziglang==0.14.1'
    assert ds1.index(install) < ds1.index('python tools/check_plugin.py ds1')
    assert all(install not in text for name, text in workflows.items() if name != 'ds1-checks.yml')
    assert ds1 == (check_plugin.WORKFLOWS/'ds1-checks.yml').read_text(encoding='utf-8')


@pytest.fixture
def compiler(tmp_path, monkeypatch):
    package = tmp_path/'ziglang'
    package.mkdir()
    executable = package/('zig.exe' if build.os.name == 'nt' else 'zig')
    executable.write_bytes(b'synthetic compiler path; never executed')
    monkeypatch.delenv('LEXEDITOR_ZIG', raising=False)
    monkeypatch.setattr(build.shutil, 'which', lambda name: None)
    monkeypatch.setattr(build.importlib.util, 'find_spec',
                        lambda name: SimpleNamespace(origin=str(package/'__init__.py')))
    return executable


def test_installed_python_distribution_is_discovered_without_starting_it(compiler):
    assert build.find_zig(None) == str(compiler)


def test_explicit_compiler_still_wins_over_python_distribution(compiler, tmp_path):
    explicit = tmp_path/'selected-compiler'
    explicit.write_bytes(b'synthetic selected compiler')
    assert build.find_zig(str(explicit)) == str(explicit)


def test_missing_distribution_executable_is_not_returned(compiler, monkeypatch):
    compiler.unlink()
    monkeypatch.setattr(build.tempfile, 'gettempdir', lambda: str(compiler.parent))
    with pytest.raises(SystemExit, match='Zig was not found'):
        build.find_zig(None)
