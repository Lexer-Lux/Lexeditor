"""Verify the FFNx Fast Start source gate without modifying build sources."""
from pathlib import Path
from tempfile import TemporaryDirectory
import shutil
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from games.ff8.fast_start_ffnx import apply

with TemporaryDirectory(prefix='ff8-fast-start-') as tmp:
    root = Path(tmp)
    for name in ('src/cfg.cpp', 'src/cfg.h', 'src/ff8_opengl.cpp', 'misc/FFNx.toml'):
        target = root / name
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(ROOT / '_scratch/ffnx-upstream' / name, target)
    apply(root, check_revision=False)
    callback = (root / 'src/ff8_opengl.cpp').read_text()
    start = callback.index('uint32_t ff8_credits_main_loop_gfx_begin_scene(')
    stop = callback.index('int credits_controller_music_play', start)
    callback = callback[start:stop]
    assert callback.index('if (enable_ff8_fast_start) stopDrawFFNxLogo();') < callback.index('drawFFNxLogoFrame(game_object)')
    assert 'return common_begin_scene(unknown, game_object);' in callback
    baseline = {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
    try:
        apply(root, check_revision=False)
    except RuntimeError:
        pass
    else:
        raise AssertionError('Repeated source extension was accepted')
    assert all(p.read_bytes() == data for p, data in baseline.items())
print('FF8 Fast Start source integration contract passed; runtime not tested')
