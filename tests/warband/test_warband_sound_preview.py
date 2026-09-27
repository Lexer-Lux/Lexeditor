from pathlib import Path
import pytest

from plugins.warband.sound_preview import sample_names, sample_path
from plugins.warband.module_records import dataset_data


def test_sound_endpoint_serves_audio_without_exposing_other_files(tmp_path, monkeypatch):
    from http.server import ThreadingHTTPServer
    from threading import Thread
    from urllib.request import urlopen
    from urllib.error import HTTPError
    from plugins.warband import server

    game = tmp_path / 'game'
    (game / 'Sounds').mkdir(parents=True)
    audio = b'RIFF\x04\x00\x00\x00WAVE'
    (game / 'Sounds' / 'one.wav').write_bytes(audio)
    (game / 'private.wav').write_bytes(b'private')
    monkeypatch.setattr(server, 'PROJECT', tmp_path / 'project')
    monkeypatch.setattr(server.paths, 'WARBAND_ROOT', game)
    http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
    thread = Thread(target=http.serve_forever, daemon=True)
    thread.start()
    try:
        base = f'http://127.0.0.1:{http.server_port}/api/sound-sample?name='
        with urlopen(base + 'one.wav') as response:
            assert response.headers['Content-Type'] in {'audio/wav', 'audio/x-wav', 'audio/vnd.wave'}
            assert response.read() == audio
        with pytest.raises(HTTPError) as refused:
            urlopen(base + '../private.wav')
        assert b'private' != refused.value.read()
    finally:
        http.shutdown()
        http.server_close()
        thread.join(timeout=5)


def test_literal_samples_allow_flags_without_executing_expressions(tmp_path):
    source='["one.wav", ("two.ogg", sf_priority_10|sf_stream_from_hd), unknown, make_sound()]'
    assert sample_names(source)==['one.wav','two.ogg']
    assert sample_names('make_sound()')==[]
    (tmp_path/'module_sounds.py').write_text('sounds=[("event",0,'+source+')]')
    assert dataset_data(tmp_path,'sounds')['rows'][0]['audioSamples']==['one.wav','two.ogg']


def test_preview_obeys_module_scan_flag_and_preserves_files(tmp_path):
    project=tmp_path/'project';module=project/'Module';game=tmp_path/'game'
    for folder in [module/'Sounds',game/'Sounds']:
        folder.mkdir(parents=True)
        (folder/'sample.wav').write_bytes(b'fixture')
    ini=module/'module.ini'
    ini.write_text('scan_module_sounds = 0\n')
    assert sample_path(project,game,'sample.wav')==game/'Sounds/sample.wav'
    ini.write_text('scan_module_sounds = 1\n')
    assert sample_path(project,game,'sample.wav')==module/'Sounds/sample.wav'
    (module/'Sounds/sample.wav').unlink()
    assert sample_path(project,game,'sample.wav')==game/'Sounds/sample.wav'
    for name in ['../private.wav','C:/private.wav','/private.wav','secret.ini','sub/../../private.wav']:
        with pytest.raises(ValueError):
            sample_path(project,game,name)
