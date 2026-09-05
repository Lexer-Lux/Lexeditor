"""Start FF8 with every completed default-off Tweak in one private runtime."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from games.ff8 import ffnx_manager, gameplay_settings, paths


def _fresh_log(path: Path, barrier_ns: int) -> str:
    if not path.is_file() or path.stat().st_mtime_ns <= barrier_ns:
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=45.0)
    args = parser.parse_args()

    game = paths.GAME_ROOT.resolve()
    config = game / "FFNx.toml"
    executable = game / "FF8_EN.exe"
    log = game / "FFNx.log"
    active_direct = paths.RUNTIME_DIRECT_ROOT.resolve()
    original_config = config.read_bytes()
    process: subprocess.Popen[bytes] | None = None
    barrier_ns = time.time_ns()

    try:
        with tempfile.TemporaryDirectory(prefix="lexeditor-complete-tweaks-") as raw:
            runtime = Path(raw).resolve()
            for name in ffnx_manager.RUNTIME_LINK_NAMES:
                (runtime / name).mkdir(parents=True, exist_ok=True)
            hext = runtime / "hext" / "ff8" / "en_nv"
            hext.mkdir(parents=True)
            direct = runtime / "direct" / "lexeditor"
            direct.mkdir(parents=True)
            (direct / "gameplay.toml").write_text(
                "schemaVersion = 1\nsharedMagicInventory = false\nmagicStockLimit = 100\n",
                encoding="utf-8", newline="\n",
            )
            patch = gameplay_settings.build_hext(
                25,
                auto_sort=True,
                single_gf_enabled=True,
                universal_item=True,
                draw_once_per_enemy=True,
                better_card_enabled=True,
                scanned_target_scan=False,
                # Party Switch is fail closed. The only proved replacement
                # callback belongs to encounter 0x01FF, not normal battles.
                party_switch=False,
                fixed_command_menu_enabled=True,
                auto_sort_magic=True,
                true_atb_wait=True,
                formulae_rework=False,
                modern_controls=True,
                vibration_consolidation=True,
                better_targeting=True,
                damage_limit_removal=True,
                fast_start_enabled=True,
                enhanced_ability_menu=True,
                streamlined_draw_enabled=True,
                flying_eva_enabled=True,
            )
            target = hext / "000000__completed-tweaks-check.txt"
            target.write_text(patch, encoding="utf-8", newline="\n")
            ffnx_manager._set_project_paths(config, runtime / "direct")
            gameplay_settings._set_ffnx_runtime_tweaks(
                config, xp_bars=True, hp_bars=True, better_targeting=True,
            )
            process = subprocess.Popen([str(executable)], cwd=str(game))
            deadline = time.monotonic() + args.timeout
            outcome = "timeout"
            text = ""
            while time.monotonic() < deadline:
                text = _fresh_log(log, barrier_ns)
                if "Exception " in text or "Unhandled" in text:
                    outcome = "crash"
                    break
                if "MODE_MAIN_MENU" in text:
                    outcome = "main-menu"
                    break
                if process.poll() is not None:
                    outcome = f"exited-{process.returncode}"
                    break
                time.sleep(0.25)
            print(f"outcome={outcome}")
            for line in text.splitlines():
                if any(value in line for value in (
                    "Applied Hext", "MODE_MAIN_MENU", "Exception", "Unhandled",
                )):
                    print(line)
            return 0 if outcome == "main-menu" else 1
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        config.write_bytes(original_config)
        ffnx_manager._set_project_paths(config, active_direct)


if __name__ == "__main__":
    raise SystemExit(main())
