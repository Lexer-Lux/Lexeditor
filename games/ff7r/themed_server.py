"""FF7R service wrapper that adds the game-specific editor theme surface."""

from __future__ import annotations

from http.server import ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from . import server as base
from .theme import theme_asset_file, theme_payload


_FRAMEWORK_CSS = '  <link rel="stylesheet" href="/shared/framework.css">'
_THEME_CSS = '  <link rel="stylesheet" href="/theme/ff7r.css">'
_THEME_JS = '  <script src="/theme/ff7r.js"></script>'
_BODY_CLOSE = "</body>"


def themed_editor_html() -> str:
    """Inject FF7R-only theme resources without forking the editor document."""
    source = (base.PLUGIN_ROOT / "editor.html").read_text(encoding="utf-8")
    if source.count(_FRAMEWORK_CSS) != 1 or source.count(_BODY_CLOSE) != 1:
        raise RuntimeError("FF7R editor theme anchors drifted; refusing ambiguous HTML injection")
    source = source.replace(_FRAMEWORK_CSS, _FRAMEWORK_CSS + "\n" + _THEME_CSS, 1)
    # The shared shell's mount call applies the legacy plugin accent. Run the
    # theme bootstrap after the editor script so the FF7R theme owns the final
    # palette instead of being partially overwritten during mountShell().
    source = source.replace(_BODY_CLOSE, _THEME_JS + "\n" + _BODY_CLOSE, 1)
    return source


class Handler(base.Handler):
    def send_text(self, text: str, content_type: str) -> None:
        data = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        try:
            if path == "/":
                return self.send_text(themed_editor_html(), "text/html")
            if path == "/theme/ff7r.css":
                return self.send_file(base.PLUGIN_ROOT / "theme.css")
            if path == "/theme/ff7r.js":
                return self.send_file(base.PLUGIN_ROOT / "theme.js")
            if path == "/api/theme":
                return self.send_json(theme_payload(
                    base.GAME_ROOT,
                    base.DATA_ROOT,
                    scan=query.get("scan") == ["1"],
                ))
            if path.startswith("/theme-assets/"):
                relative = unquote(path.removeprefix("/theme-assets/"))
                target = theme_asset_file(base.DATA_ROOT, relative)
                if target is None:
                    return self.send_json({"error": "FF7R theme asset not found"}, 404)
                return self.send_file(target)
        except Exception as error:
            return self.send_json({"error": str(error)}, 500)
        return super().do_GET()


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", base.PORT), Handler).serve_forever()
