"""Synthetic card atlas/archive and actual HTTP endpoint regression tests.

No FF8 game data is included or required. The fixtures implement the published
SP2/TEX format, with distinct colors for every card and page. This does not
claim visual acceptance against an installed game's images.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
import struct
import sys
import tempfile
import threading
from urllib.request import build_opener, ProxyHandler
from urllib.error import HTTPError
from unittest.mock import patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from games.ff8 import card_art, server


def sp2() -> bytes:
    data = bytearray(4 + 11*4 + 11*12)
    struct.pack_into('<I', data, 0, 11)
    for slot in range(11):
        offset = 48 + slot*12
        struct.pack_into('<H', data, 4 + slot*4, offset)
        data[offset+4:offset+12] = bytes(((slot%4)*62, (slot//4)*88, 1, 0, 62, 0, 88, 0))
    return bytes(data)


def color(page: int, slot: int) -> tuple[int, int, int, int]:
    return (page*20, slot*20, (page*11+slot)*2, 255)


def texture(page: int) -> bytes:
    header = bytearray(240)
    for offset, value in [(0,2),(0x30,1),(0x34,256),(0x38,8),(0x3C,256),
                          (0x40,264),(0x4C,1),(0x58,256),(0x68,1)]:
        struct.pack_into('<I',header,offset,value)
    palette = bytearray(1024)
    pixels = bytearray(256*264)
    for slot in range(11):
        red,green,blue,alpha = color(page,slot)
        palette[slot*4:slot*4+4] = bytes((blue,green,red,alpha))
        x,y = slot%4*62,slot//4*88
        for line in range(y,y+88):
            pixels[line*256+x:line*256+x+62] = bytes([slot])*62
    return bytes(header+palette+pixels)


def archive(prefix: Path):
    contents = {'cardanm.sp2':sp2(), **{f'mc{i:02}.tex':texture(i) for i in range(10)}}
    data,index = bytearray(),bytearray()
    for name,value in contents.items():
        index += struct.pack('<III',len(value),len(data),0)
        data += value
    prefix.with_suffix('.fs').write_bytes(data)
    prefix.with_suffix('.fi').write_bytes(index)
    prefix.with_suffix('.fl').write_text('\n'.join(contents)+'\n',encoding='utf-8')


def check_png(raw: bytes, card_id: int):
    image = Image.open(BytesIO(raw)).convert('RGBA')
    assert image.size == (62,88)
    assert image.getpixel((0,0)) == image.getpixel((61,87)) == color(card_id//11,card_id%11)


def main():
    for card_id in range(110):
        check_png(card_art.decode_card(sp2(),texture(card_id//11),card_id),card_id)
    invalid = [(-1,sp2(),texture(0)),(110,sp2(),texture(0)),(0,b'bad',texture(0)),
               (0,sp2(),b'bad'),(0,sp2(),texture(0)[:-1])]
    index = bytearray(sp2());struct.pack_into('<H',index,4,65530)
    invalid.append((0,index,texture(0)))
    index = bytearray(sp2());index[48+8]=0
    invalid.append((0,index,texture(0)))
    for card_id,index,tex in invalid:
        try:
            card_art.decode_card(index,tex,card_id)
        except ValueError:
            pass
        else:
            raise AssertionError('Malformed card image was accepted')
    print('PASS 110 card/page mappings, BGRA palette conversion, bounds and malformed inputs')
    with tempfile.TemporaryDirectory(prefix='lexeditor-card-art-') as directory:
        prefix = Path(directory)/'menu'
        archive(prefix)
        card_art._archive_card.cache_clear()
        with patch.dict(card_art.paths.ARCHIVES,{'menu':prefix}):
            check_png(card_art.card_png(109),109)
            assert card_art.card_png(109) == card_art.card_png(109)
            before = card_art._archive_card.cache_info()
            # Replacing one palette color invalidates the archive fingerprint.
            fs = prefix.with_suffix('.fs')
            data = bytearray(fs.read_bytes());data[len(sp2())+240+2] = 201;fs.write_bytes(data)
            assert Image.open(BytesIO(card_art.card_png(0))).getpixel((0,0))[0] == 201
            assert card_art._archive_card.cache_info().misses == before.misses+1
            archive(prefix)
            service = server.create_server(0)
            thread = threading.Thread(target=service.serve_forever,daemon=True)
            thread.start()
            try:
                opener = build_opener(ProxyHandler({}))
                base = f'http://127.0.0.1:{service.server_port}'
                for card_id in (0,10,11,109):
                    with opener.open(f'{base}/assets/cards/{card_id}.png',timeout=5) as response:
                        assert response.headers.get_content_type() == 'image/png'
                        check_png(response.read(),card_id)
                for path in ('/enemies_ui.js','/enemies_ui.css'):
                    with opener.open(base+path,timeout=5) as response:
                        assert response.status == 200 and response.read()
                for path in ('/assets/cards/255.png','/assets/cards/not-an-id.png'):
                    try:
                        opener.open(base+path,timeout=5)
                    except HTTPError as error:
                        assert error.code == 400
                    else:
                        raise AssertionError('Invalid card ID endpoint succeeded')
            finally:
                service.shutdown();service.server_close();thread.join(timeout=5)
        card_art._archive_card.cache_clear()
    print('PASS production FS archive, cache invalidation, PNG and UI asset HTTP routes')


if __name__ == '__main__':
    main()
