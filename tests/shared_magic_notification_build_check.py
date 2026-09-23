"""Check notification integration against the exact packaged runtime source."""
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from prepare_ff8_native_build import integrate_shared_magic_notifications

patch = (ROOT/'plugins/ff8/ffnx_issue_51/package/ISSUE51_DERIVATIVE_SOURCE.patch').read_text(encoding='utf-8')
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
    # The message goes to Lexeditor's own FF8-style box, which owns the queue
    # and the drawing. FFNx's popup fades on an accelerating decay tuned for
    # one-word notices, faster than a sentence can be read, and it looks like
    # the injector rather than like the game.
    assert '#include "../lexeditor_ff8_toast.h"' in built
    assert 'lexeditor_ff8_toast_push(message.c_str(), true)' in built
    assert '#include "../toast_queue.h"' not in built
    assert 'g_lexeditor_toasts' not in built
    heartbeat = built.split('void ff8_shared_magic_heartbeat()\n{', 1)[1]
    # Nothing is drained here any more: the box does that in the render frame.
    assert 'lexeditor_toast::' not in heartbeat
    integrate_shared_magic_notifications(root)
    assert path.read_text(encoding='utf-8') == built

# The box itself: the parts that need no device are checked here, because the
# drawing cannot be exercised without one.
layout = (ROOT/'plugins/ff8/ffnx_toasts/toast_layout.h').read_text(encoding='utf-8')
toast = (ROOT/'plugins/ff8/ffnx_toasts/ffnx-src/lexeditor_ff8_toast.cpp').read_text(encoding='utf-8')
header = (ROOT/'plugins/ff8/ffnx_toasts/ffnx-src/lexeditor_ff8_toast.h').read_text(encoding='utf-8')
assert 'lexeditor_toast::layout(' in toast and 'lexeditor_toast::fade(' in toast
assert 'ImGui::GetForegroundDrawList()' in toast
assert 'show_popup_msg' not in toast, 'the box draws itself; it does not wrap the popup'
assert 'projectGamePointToScreen' in toast, 'game coordinates, or the box moves with the window'
for name in ('lexeditor_ff8_toast_push', 'lexeditor_ff8_toast_draw',
             'lexeditor_ff8_toast_enabled', 'lexeditor_ff8_toast_poll_battle'):
    assert name in header and name in toast

# The refusal sentence is written twice - once where Summon is greyed, once
# where the reason is shown - so they are checked against each other.
sys.path.insert(0, str(ROOT))
from plugins.ff8 import battle_issue_54 as battle
quoted = toast.split('LEXEDITOR_SUMMON_UNAVAILABLE_REASON =', 1)[1].split(';', 1)[0]
spoken = ''.join(part.split('"')[1] for part in quoted.split('\n') if '"' in part)
assert spoken == battle.SUMMON_UNAVAILABLE_REASON, (spoken, battle.SUMMON_UNAVAILABLE_REASON)
assert hex(battle.SUMMON_REFUSED_FLAG)[2:].upper() in toast.upper(), (
    'the box reads the flag the battle patch raises'
)

print('Notification integration passes: the message goes to FF8\'s own box, held long enough to read, and the refused-Summon sentence matches the patch that greys it.')
