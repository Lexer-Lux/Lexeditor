"""FFNx.toml audio-layer gains for issue #498 (SFX/Music sliders backend)."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plugins.ff8.ffnx_manager import set_audio_volumes


BASE = "use_external_sfx = true\nexternal_sfx_volume = -1\nexternal_music_volume = -1\n"


def write_config(path, text=BASE):
    config = Path(path) / "FFNx.toml"
    config.write_text(text, encoding="utf-8")
    return config


def test_replaces_existing_gains(tmp_path):
    config = write_config(tmp_path)
    assert set_audio_volumes(config, sfx=80, music=60) == {
        "external_sfx_volume": 80, "external_music_volume": 60}
    text = config.read_text(encoding="utf-8")
    assert "external_sfx_volume = 80" in text
    assert "external_music_volume = 60" in text
    assert "-1" not in text


def test_appends_missing_keys(tmp_path):
    config = write_config(tmp_path, "use_external_sfx = true\n")
    assert set_audio_volumes(config, music=45) == {"external_music_volume": 45}
    assert "external_music_volume = 45" in config.read_text(encoding="utf-8")


def test_none_side_preserves_auto_detect(tmp_path):
    config = write_config(tmp_path)
    assert set_audio_volumes(config, sfx=70) == {"external_sfx_volume": 70}
    text = config.read_text(encoding="utf-8")
    assert "external_sfx_volume = 70" in text
    assert "external_music_volume = -1" in text


def test_no_sides_writes_nothing(tmp_path):
    config = write_config(tmp_path)
    before = config.stat().st_mtime_ns
    assert set_audio_volumes(config) == {}
    assert config.stat().st_mtime_ns == before


@pytest.mark.parametrize("bad", (-1, 101, "80", 80.0, True))
def test_rejects_out_of_range_gains(tmp_path, bad):
    config = write_config(tmp_path)
    with pytest.raises(ValueError):
        set_audio_volumes(config, sfx=bad)
    with pytest.raises(ValueError):
        set_audio_volumes(config, music=bad)
    assert config.read_text(encoding="utf-8") == BASE
