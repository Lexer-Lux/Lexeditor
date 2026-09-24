"""Lexeditor's ReShade effects are switched and tuned through the game's preset."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from core import reshade_effects as fx
from core import reshade_projects as rp


def test_every_bundled_effect_exposes_its_controls():
    effects = {effect["id"]: effect for effect in fx.catalogue()}
    assert list(effects)[:1] == ["AmbientOcclusion"] and list(effects)[-1] == "Compare"
    colors = {row["name"]: row for row in effects["Colors"]["controls"]}
    assert set(colors) == {"Brightness", "Contrast", "Saturation", "Vibrance", "Gamma"}
    assert colors["Gamma"]["min"] == 0.5 and colors["Gamma"]["default"] == 1.0
    vignette = {row["name"]: row for row in effects["Vignette"]["controls"]}
    assert vignette["Shape"]["items"] == ["Round", "Screen-shaped"]
    # A runtime-fed uniform is not a control.
    assert "FrameTime" not in {row["name"] for row in effects["DepthOfField"]["controls"]}


def test_switching_effects_writes_the_preset_reshade_loads(tmp_path):
    game = tmp_path
    (game / rp.RESHADE_INI).write_text("[GENERAL]\nPresetPath=.\\Mine.ini\n", encoding="utf-8")
    fx.set_enabled(game, "Bloom.fx", True)
    fx.set_enabled(game, "Compare.fx", True)
    fx.set_enabled(game, "Colors.fx", True)
    top, _ = fx.read_preset(game / "Mine.ini")
    assert top["Techniques"] == "Compare@Compare.fx,Bloom@Bloom.fx,Colors@Colors.fx,CompareShow@Compare.fx"
    fx.set_enabled(game, "Bloom.fx", False)
    assert "Bloom@Bloom.fx" not in fx.read_preset(game / "Mine.ini")[0]["Techniques"]


def test_values_are_clamped_and_read_back(tmp_path):
    fx.set_value(tmp_path, "Colors.fx", "Gamma", 9)
    fx.set_value(tmp_path, "Vignette.fx", "Shape", 1)
    rows = {row["id"]: row for row in fx.state(tmp_path)["effects"]}
    assert rows["Colors"]["values"]["Gamma"] == 2.0
    assert rows["Vignette"]["values"]["Shape"] == 1
    with pytest.raises(ValueError):
        fx.set_value(tmp_path, "Colors.fx", "Nope", 1)


def test_defaults_round_trip_and_drop_foreign_effects(tmp_path):
    game = tmp_path / "game"; game.mkdir()
    defaults = tmp_path / "reshade-defaults.ini"
    fx.write_preset(game / fx.DEFAULT_PRESET, {"Techniques": "Sketch@Sketch.fx,Colors@Colors.fx"},
                    {"Sketch.fx": {"A": "1"}, "Colors.fx": {"Contrast": "0.250000"}})
    fx.save_defaults(game, defaults)
    top, sections = fx.read_preset(defaults)
    assert top["Techniques"] == "Colors@Colors.fx" and "Sketch.fx" not in sections
    fx.set_value(game, "Colors.fx", "Contrast", -1)
    fx.reset(game, defaults)
    assert {row["id"]: row for row in fx.state(game, defaults)["effects"]}["Colors"]["values"]["Contrast"] == 0.25
    assert fx.state(game, defaults)["hasDefaults"]


def test_without_defaults_reset_turns_everything_off(tmp_path):
    fx.set_enabled(tmp_path, "Colors.fx", True)
    fx.reset(tmp_path, None)
    assert not any(row["enabled"] for row in fx.state(tmp_path)["effects"])
