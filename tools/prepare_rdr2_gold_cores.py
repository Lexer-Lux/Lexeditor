"""Build transparent gold-fill masks from locally extracted stock core artwork.

Game artwork stays in private output. Existing resident dictionary textures are
preserved byte for byte. This tool does not install or alter game files.
"""
from pathlib import Path
import argparse
import hashlib
import json
import tempfile

from PIL import Image

FAMILIES = ('health', 'stamina', 'deadeye', 'horse_health', 'horse_stamina')
PREFIX = 'lex_gold_core_'


def pixels(image):
    reader = getattr(image, 'get_flattened_data', image.getdata)
    return list(reader())


def masks(states):
    """Remove the grey unfilled glyph instead of tinting it gold.

    State 0 and state 15 give the per-pixel dark/light endpoints. A staged
    state's position between them gives its fill alpha. Max accumulation removes
    tiny compression flicker between increasing stock states.
    """
    if len(states) != 16 or any(s.size != states[0].size for s in states):
        raise ValueError('Sixteen equal-size core states are required')
    arrays = [pixels(s.convert('RGBA')) for s in states]
    empty, full = arrays[0], arrays[-1]
    dark = [sum(p[:3]) for p in empty]
    span = [sum(p[:3])-d for p, d in zip(full, dark)]
    coverage = [p[3] for p in full]
    last = [0] * len(full)
    result = []
    for index, state in enumerate(arrays):
        alpha = []
        for pixel, d, delta, cap, previous in zip(state, dark, span, coverage, last):
            fraction = max(0, min(1, (sum(pixel[:3])-d)/delta)) if delta > 48 and cap else 0
            alpha.append(max(previous, round(fraction*cap)))
        if index == 0:
            alpha = [0] * len(full)
        if index == 15:
            alpha = coverage.copy()
        image = Image.new('RGBA', states[0].size)
        image.putdata([(255, 255, 255, a) for a in alpha])
        result.append(image)
        last = alpha
    base = Image.new('RGBA', states[0].size)
    base.putdata([(255, 255, 255, a) for a in coverage])
    return base, result



def texture_fingerprint(texture):
    return hashlib.sha256(texture.to_dds_bytes()).hexdigest()


def build(source: Path, resident: Path, output: Path):
    from texfury import ITD, Texture, BCFormat, RscCompression
    dictionary = ITD.load(resident)
    before = {t.name: texture_fingerprint(t) for t in dictionary.textures
              if not t.name.startswith(PREFIX)}
    for name in list(dictionary.names()):
        if name.startswith(PREFIX):
            dictionary.remove(name)
    previews = output.parent / 'core-previews'
    previews.mkdir(parents=True, exist_ok=True)
    for family in FAMILIES:
        stock = ITD.load(source / f'{family}-normalized.ytd')
        expected = {f'core_state_{i}' for i in range(16)}
        if set(stock.names()) != expected:
            raise ValueError(f'Unexpected stock core states: {family}')
        base, frames = masks([stock.get(f'core_state_{i}').to_pil() for i in range(16)])
        for suffix, picture in [('base', base)] + [(str(i), im) for i, im in enumerate(frames)]:
            name = PREFIX + family + '_' + suffix
            dictionary.add(Texture.from_pil(picture, name=name,
                           format=BCFormat.A8R8G8B8, generate_mipmaps=False))
        # The three columns show white base with full, half and near-empty gold.
        strip = Image.new('RGBA', (384, 128), (35, 35, 35, 255))
        for col, index in enumerate((15, 7, 1)):
            tile = base.copy()
            gold = Image.new('RGBA', tile.size, (255, 196, 64, 0))
            gold.putalpha(frames[index].getchannel('A'))
            tile = Image.alpha_composite(tile, gold)
            strip.alpha_composite(tile, (128*col, 0))
        strip.save(previews / f'{family}.png')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='lex-core-build-') as temp:
        candidate = Path(temp) / 'generic_textures.ytd'
        dictionary.save(candidate, compression=RscCompression.DEFLATE)
        checked = ITD.load(candidate)
        after = {t.name: texture_fingerprint(t) for t in checked.textures
                 if not t.name.startswith(PREFIX)}
        if before != after:
            raise ValueError('Resident texture preservation check failed')
        for family in FAMILIES:
            frames = [pixels(checked.get(PREFIX+family+'_'+str(i)).to_pil().getchannel('A'))
                      for i in range(16)]
            if any(frames[0]) or any(any(y < x for x, y in zip(a, b)) for a, b in zip(frames, frames[1:])):
                raise ValueError('Core alpha progression failed after dictionary round trip')
        output.write_bytes(candidate.read_bytes())
    report = {'preserved_textures': len(before), 'added_textures': 85,
              'bytes': output.stat().st_size,
              'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
              'resident_sha256': hashlib.sha256(resident.read_bytes()).hexdigest(),
              'stock_sha256': {family: hashlib.sha256(
                  (source / f'{family}-normalized.ytd').read_bytes()).hexdigest()
                  for family in FAMILIES}}
    output.with_suffix('.report.json').write_text(json.dumps(report, indent=2), 'utf-8')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--resident', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve() == args.resident.resolve():
        parser.error('Build output must be separate from the resident input')
    print(json.dumps(build(args.source, args.resident, args.output)))


if __name__ == '__main__':
    main()
