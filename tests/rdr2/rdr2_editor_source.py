"""Read the RDR2 page and the local scripts/styles it actually loads."""
from html.parser import HTMLParser
from pathlib import Path


def editor_source() -> str:
    root = Path(__file__).resolve().parents[2] / 'plugins' / 'rdr2'
    html = (root / 'editor.html').read_text(encoding='utf-8')
    files = []

    class Assets(HTMLParser):
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            reference = attrs.get('src') if tag == 'script' else (
                attrs.get('href') if tag == 'link' and attrs.get('rel') == 'stylesheet' else None)
            if reference and not reference.startswith('/') and '://' not in reference:
                path = (root / reference).resolve()
                if not path.is_relative_to(root.resolve()):
                    raise ValueError(f'Unexpected editor asset path: {reference}')
                files.append(path)

    Assets().feed(html)
    return '\n'.join([html, *(path.read_text(encoding='utf-8') for path in files)])
