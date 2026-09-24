from pathlib import Path
from unittest.mock import Mock, patch

from core.desktop_host import HostApi


def test_location_lookup_does_not_open_explorer():
    host=HostApi.__new__(HostApi)
    host._plugins={'ff8':object()}
    host._installations=Mock()
    host._installations.snapshot.return_value={}
    target=Path('C:/Game/data/kernel.bin')
    with patch('core.game_data_location.find_original_location',return_value=target), patch('core.desktop_host.subprocess.Popen') as opened:
        assert host.game_data_location('ff8','kernel.bin')=={'path':str(target)}
        opened.assert_not_called()
        host.open_game_data_location('ff8','kernel.bin')
        opened.assert_called_once_with(['explorer.exe','/select,',str(target)])
