"""Check notification integration against the exact packaged runtime source."""
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from prepare_ff8_native_build import integrate_shared_magic_notifications

patch = (ROOT/'games/ff8/ffnx_issue_51/package/ISSUE51_DERIVATIVE_SOURCE.patch').read_text(encoding='utf-8')
section = patch.split('+++ b/src/ff8/shared_magic_runtime.cpp\n', 1)[1].split('diff --git ', 1)[0]
source = '\n'.join(line[1:] for line in section.splitlines() if line.startswith('+'))+'\n'
with tempfile.TemporaryDirectory(prefix='lex-shared-toast-') as folder:
    root = Path(folder)
    path = root/'src/ff8/shared_magic_runtime.cpp'
    path.parent.mkdir(parents=True)
    path.write_text(source, encoding='utf-8')
    integrate_shared_magic_notifications(root)
    result = path.read_text(encoding='utf-8')
    assert 'migration_warning_template(result.error, g_stock_limit)' in result
    heartbeat = result.split('void ff8_shared_magic_heartbeat()\n{', 1)[1]
    assert heartbeat.index('show_popup_msg(') < heartbeat.index('g_last_heartbeat_tick')
    assert '!g_activation_toast.empty() && get_popup_time() == 0' in heartbeat
    assert 'g_activation_toast.clear();' in heartbeat
    activation = result.split('const ActivationResult result = activate_runtime', 1)[1].split('template<std::size_t N>', 1)[0]
    assert 'show_popup_msg(' not in activation
    assert 'write_saved(candidate)' not in activation.split('return;', 1)[0]
    integrate_shared_magic_notifications(root)
    assert path.read_text(encoding='utf-8') == result
# The block above checks the PINNED patch, which is the source the shipped
# driver was built from. This one checks what the integration does to a tree
# that does not carry the message yet, which is what the next build compiles.
with tempfile.TemporaryDirectory(prefix='lex-shared-toast-fresh-') as folder:
    root = Path(folder)
    path = root/'src/ff8/shared_magic_runtime.cpp'
    path.parent.mkdir(parents=True)
    fresh = [line for line in source.splitlines(keepends=True)
             if 'g_activation_toast' not in line]
    assert len(fresh) < len(source.splitlines())
    path.write_text(''.join(fresh), encoding='utf-8')
    integrate_shared_magic_notifications(root)
    built = path.read_text(encoding='utf-8')
    # The queue owns what is shown and for how long. FFNx's overlay fades on
    # an accelerating decay, faster than a sentence can be read, so the message
    # goes through the queue and the overlay is only the surface it lands on.
    assert '#include "../toast_queue.h"' in built
    assert 'lexeditor_toast::Queue g_lexeditor_toasts' in built
    assert 'g_lexeditor_toasts.push(message, lexeditor_toast::Tone::warning)' in built
    assert 'g_lexeditor_toasts.update(' in built
    heartbeat = built.split('void ff8_shared_magic_heartbeat()\n{', 1)[1]
    assert heartbeat.index('show_popup_msg(') < heartbeat.index('g_last_heartbeat_tick')
    integrate_shared_magic_notifications(root)
    assert path.read_text(encoding='utf-8') == built

print('Notification integration passes: deferred, held long enough to read, existing popup preserved, failed stocks unchanged.')
