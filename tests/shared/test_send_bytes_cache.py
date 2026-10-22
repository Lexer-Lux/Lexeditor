"""send_bytes serves immutable bytes cacheable, everything else no-store."""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.plugin_http import NO_STORE, PluginRequestHandler


class RecordingHandler:
    def __init__(self):
        self.status = None
        self.headers = {}
        self.body = io.BytesIO()

    def send_response(self, status):
        self.status = status

    def send_header(self, key, value):
        self.headers[key] = value

    def end_headers(self):
        pass

    @property
    def wfile(self):
        return self.body


def serve(data, content_type, **kwargs):
    fake = RecordingHandler()
    PluginRequestHandler.send_bytes(fake, data, content_type, **kwargs)
    return fake


def test_bytes_default_to_no_store():
    reply = serve(b'png-bytes', 'image/png')
    assert reply.status == 200
    assert reply.headers['Content-Type'] == 'image/png'
    assert reply.headers['Cache-Control'] == NO_STORE
    assert reply.headers['Content-Length'] == str(len(b'png-bytes'))
    assert reply.body.getvalue() == b'png-bytes'


def test_explicit_cache_value_reaches_the_header():
    reply = serve(b'png-bytes', 'image/png', cache='public, max-age=31536000, immutable')
    assert reply.headers['Cache-Control'] == 'public, max-age=31536000, immutable'
    assert reply.body.getvalue() == b'png-bytes'


def test_status_passes_through():
    reply = serve(b'missing', 'text/plain', status=404)
    assert reply.status == 404
    assert reply.headers['Cache-Control'] == NO_STORE
