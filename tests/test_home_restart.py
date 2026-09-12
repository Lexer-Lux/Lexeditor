"""Home restart guards use the current host state, without a native window."""
import threading
import unittest
from unittest.mock import Mock
from desktop_host import HostApi


class HomeRestartTests(unittest.TestCase):
    def host(self):
        host = HostApi.__new__(HostApi)
        host._lock = threading.RLock()
        host._dirty_count = 0
        host._restart_requested = False
        host._close_authorized = False
        host._window = Mock()
        return host

    def test_dirty_host_refuses_even_if_home_snapshot_was_clean(self):
        host = self.host(); host.set_dirty_count(1)
        with self.assertRaisesRegex(RuntimeError, 'save or discard'):
            host.restart_lexeditor()
        host._window.destroy.assert_not_called()
        self.assertFalse(host._restart_requested)
        self.assertFalse(host._close_authorized)

    def test_repeated_restart_destroys_once(self):
        host = self.host()
        self.assertEqual(host.restart_lexeditor(), {'restarting': True})
        self.assertEqual(host.restart_lexeditor(), {'restarting': True})
        host._window.destroy.assert_called_once()

    def test_failed_destroy_restores_flags_and_can_retry(self):
        host = self.host(); host._window.destroy.side_effect = RuntimeError('window busy')
        with self.assertRaisesRegex(RuntimeError, 'window busy'): host.restart_lexeditor()
        self.assertFalse(host._restart_requested)
        self.assertFalse(host._close_authorized)
        host._window.destroy.side_effect = None
        self.assertEqual(host.restart_lexeditor(), {'restarting': True})


if __name__ == '__main__': unittest.main()
