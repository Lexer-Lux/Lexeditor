"""Every DS1 test reads an empty mod library of its own.

Apply combines every enabled mod in the library (plugins/ds1/mod_loader.py).
Without this, a test that applies would read the developer's real DS1 mod
library, and a mod switched on there would change the test's result.
"""
import pytest

from plugins.ds1 import tweak_mods,composition_cache


@pytest.fixture(autouse=True)
def _own_mod_library(tmp_path_factory, monkeypatch):
    monkeypatch.setenv(tweak_mods.MODS_ENV, str(tmp_path_factory.mktemp("ds1-library")))
    cache = tmp_path_factory.mktemp('ds1-cache')
    monkeypatch.setattr(composition_cache,'user_root',lambda:cache)
