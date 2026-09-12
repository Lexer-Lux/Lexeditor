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
print('Notification integration passes: deferred, once only, existing popup preserved, failed stocks unchanged.')
