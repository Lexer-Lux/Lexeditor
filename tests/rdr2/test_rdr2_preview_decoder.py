"""R2-2: preview availability fails closed when the decoder cannot load.

The check used to look only for the decoder file, so under a CPython the
bundled .pyd was not built for, an item read as available and the drawer
opened onto a DLL error. Availability now imports the decoder once and
reports the failure as the reason instead.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# Imported as a package module: a bare import put RDR2's paths.py into
# sys.modules as "paths", and later plugins that import their own bare
# paths module (Warband) then failed to collect.
from plugins.rdr2 import model_preview  # noqa: E402


@pytest.fixture
def fresh_decoder_probe(monkeypatch):
    monkeypatch.setattr(model_preview, "_DECODER_PROBE", None)
    yield
    monkeypatch.setattr(model_preview, "_DECODER_PROBE", None)


def test_unloadable_decoder_reports_its_reason(monkeypatch, tmp_path, fresh_decoder_probe):
    game = tmp_path / "game"
    game.mkdir()
    tool = tmp_path / "RpfCli.exe"
    tool.write_bytes(b"x")
    decoder = tmp_path / "pylibdrawable.pyd"
    decoder.write_bytes(b"x")
    monkeypatch.setattr(model_preview, "GAME_ROOT", game)
    monkeypatch.setattr(model_preview, "RPF_TOOL", tool)
    monkeypatch.setattr(model_preview, "DECODER", decoder)

    def boom():
        raise ImportError("DLL load failed while importing pylibdrawable")

    monkeypatch.setattr(model_preview, "_decoder_module", boom)
    result = model_preview.model_preview_availability("w_revolver_cattleman01")
    assert result["available"] is False
    assert "decoder" in result["reason"]
    assert "DLL load failed" in result["reason"]


def test_decoder_probe_imports_once(monkeypatch, fresh_decoder_probe):
    calls = []

    def ok():
        calls.append(1)
        return object()

    monkeypatch.setattr(model_preview, "_decoder_module", ok)
    assert model_preview._decoder_probe() == (True, "")
    assert model_preview._decoder_probe() == (True, "")
    assert calls == [1]
