from pathlib import Path
import sys,tempfile,ast,math,re
sys.path.insert(0,str(Path.cwd()))
from game_data_location import find_original_location
with tempfile.TemporaryDirectory() as td:
 root=Path(td);cache=root/'cache';cache.mkdir();game=root/'game';game.mkdir();(cache/'menu').mkdir();target=cache/'menu'/'a.bin';target.write_bytes(b'original');(game/'lml').mkdir();(game/'lml'/'a.bin').write_bytes(b'mod')
 assert find_original_location('menu/a.bin',[cache],game)==target
 assert find_original_location('a.bin',[cache],game)==target
 try:find_original_location('../a.bin',[cache],game)
 except ValueError:pass
 else:raise AssertionError('traversal')
 try:find_original_location('a.bin',[],game)
 except FileNotFoundError:pass
 else:raise AssertionError('mod selected as original')
 (game/'FF8_EN.exe').write_bytes(b'exe')
 assert find_original_location('ff8/en/exe/card_names.msd',[cache],game)==game/'FF8_EN.exe'
# Group rows reveal the common original folder; an explicit archive member can
# fall back to its installed source archive, without extracting or executing it.
with tempfile.TemporaryDirectory() as td:
 root=Path(td);prepared=root/'prepared';prepared.mkdir();game=root/'game';game.mkdir()
 for name in ('a.xml','b.xml'):(prepared/name).write_bytes(b'original')
 assert find_original_location('*.xml',[prepared],game)==prepared
 assert find_original_location('a.xml + b.xml',[prepared],game)==prepared
 archive=game/'content.rpf';archive.write_bytes(b'archive')
 assert find_original_location('content.rpf:/missing/member.xml',[prepared],game)==archive
 assert find_original_location('game/content.rpf:/missing/member.xml',[prepared],game)==archive
 (game/'game').mkdir();installed_archive=game/'game'/'content.rpf';installed_archive.write_bytes(b'archive')
 assert find_original_location('game/content.rpf:/missing/member.xml',[prepared],game)==installed_archive

 (prepared/'content').mkdir();(prepared/'content'/'inventory.xml').write_bytes(b'original')
 assert find_original_location('game/content.rpf:/content/inventory.xml',[prepared],game)==prepared/'content'/'inventory.xml'

source=ast.parse(Path('games/rdr2/server.py').read_text(encoding='utf-8'));node=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='_validate_mob_value');ns={'re':re};exec(compile(ast.Module(body=[node],type_ignores=[]),'mob scalar validation','exec'),ns);validate=ns['_validate_mob_value']
for value in ('nan','inf','nope',''):
 try:validate('1.0',value,set())
 except ValueError:pass
 else:raise AssertionError(value)
assert validate('1.0','2.5',set())=='2.5'
assert validate('CA_POOR','CA_AVERAGE',{'CA_POOR','CA_AVERAGE'})=='CA_AVERAGE'
try:validate('CA_POOR','MADE_UP',{'CA_POOR','CA_AVERAGE'})
except ValueError:pass
else:raise AssertionError('unknown enum')
from games.rdr2.data_map import build_data_map
rows=build_data_map(Path(r'C:\RDR2Mod\DATA_MAP.md'))['rows'];assert len(rows)>100
print('Original file resolution, typed Mobs values and full RDR2 Data Map parsing passed:',len(rows),'rows')
