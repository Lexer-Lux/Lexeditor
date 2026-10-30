"""Mod-owned weapon skill records and exact weapon assignments, without gameplay presets."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from core.plugin_files import atomic_write
from .tweak_mods import checked
from .deployment import _assert_disjoint

RELATIVE = Path('script/weapon_skills.json')
TABLE = 'WeaponSkill'
TAB = 'ashes-of-war'
LIMIT = 1024 * 1024
EMPTY = {'version': 1, 'skills': [], 'assignments': []}
KEYS = {'id', 'name', 'description', 'iconId', 'fpCost', 'staminaCost'}


def integer(value, lower, upper, label):
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError(f'{label} must be a whole number from {lower} to {upper}')
    return value


def validate(value, weapon_ids=None):
    if not isinstance(value, dict) or set(value) != set(EMPTY) or type(value['version']) is not int or value['version'] != 1:
        raise ValueError('Unsupported weapon-skill catalog')
    if not isinstance(value['skills'], list) or len(value['skills']) > 4096:
        raise ValueError('A weapon-skill catalog supports at most 4096 skills')
    skills, ids = [], set()
    for entry in value['skills']:
        if not isinstance(entry, dict) or set(entry) != KEYS:
            raise ValueError('A weapon skill has unsupported fields')
        identity = integer(entry['id'], 1, 2147483647, 'Skill ID')
        if identity in ids:
            raise ValueError('Weapon skill IDs must be unique')
        ids.add(identity)
        name, description = entry['name'], entry['description']
        if not isinstance(name, str) or not name.strip() or len(name) > 80 or any(ord(c) < 32 for c in name):
            raise ValueError('A skill needs a name of at most 80 characters')
        if not isinstance(description, str) or len(description) > 2000 or '\0' in description:
            raise ValueError('A skill description supports at most 2000 characters')
        if entry['iconId'] is not None:
            integer(entry['iconId'], 0, 65535, 'Icon')
        for key in ('fpCost', 'staminaCost'):
            integer(entry[key], 0, 65535, key)
        skills.append(deepcopy(entry))
    if not isinstance(value['assignments'], list) or len(value['assignments']) > 32768:
        raise ValueError('A catalog supports at most 32768 weapon assignments')
    assignments, assigned = [], set()
    for entry in value['assignments']:
        if not isinstance(entry, dict) or set(entry) != {'weaponId', 'skillId'}:
            raise ValueError('Unsupported weapon-skill assignment')
        weapon = integer(entry['weaponId'], 0, 2147483647, 'Weapon ID')
        skill = integer(entry['skillId'], 1, 2147483647, 'Skill ID')
        if weapon in assigned:
            raise ValueError('A weapon has more than one assigned skill')
        if skill not in ids:
            raise ValueError('Choose an existing Ash of War')
        if weapon_ids is not None and weapon not in weapon_ids:
            raise ValueError('Choose a weapon the game knows')
        assigned.add(weapon); assignments.append(dict(entry))
    return {'version': 1, 'skills': skills, 'assignments': assignments}


def read(root, weapon_ids=None):
    path = checked(Path(root) / RELATIVE)
    if not path.exists():
        return deepcopy(EMPTY), None
    if not path.is_file() or path.stat().st_size > LIMIT:
        raise ValueError('The weapon-skill catalog is too large or not a file')
    raw = path.read_bytes()
    if len(raw) > LIMIT:
        raise ValueError('The weapon-skill catalog is too large')
    return validate(json.loads(raw), weapon_ids), hashlib.sha256(raw).hexdigest()


class WeaponSkills:
    def __init__(self, game_root, project=None, read_only=True):
        self.game_root = Path(game_root)
        self.project = checked(Path(project)) if project else None
        self.read_only = read_only or self.project is None
        if self.project:
            _assert_disjoint(self.game_root, self.project)
        self.saved, self.saved_hash = read(self.project) if self.project else (deepcopy(EMPTY), None)
        self.value = deepcopy(self.saved)

    def editable(self):
        if self.read_only:
            raise PermissionError('Select or create a mod before editing Ashes of War')
        _assert_disjoint(checked(self.game_root), checked(self.project))

    @property
    def dirty_count(self):
        return int(self.value != self.saved)

    def pending_changes(self):
        return [{'table': TABLE, 'name': 'Ashes of War', 'field': 'Skills and weapon assignments',
                 'file': RELATIVE.as_posix()}] if self.dirty_count else []

    def validate_save(self):
        if not self.dirty_count:
            return
        self.editable()
        _, current = read(self.project)
        if current != self.saved_hash:
            raise ValueError('The weapon-skill catalog changed on disk. Reload the mod before saving.')
        validate(self.value)

    def save(self):
        self.validate_save()
        if not self.dirty_count:
            return
        raw = (json.dumps(self.value, ensure_ascii=False, indent=2) + '\n').encode()
        if len(raw) > LIMIT:
            raise ValueError('The weapon-skill catalog is too large')
        path = checked(self.project / RELATIVE)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(path, raw)
        self.saved = deepcopy(self.value); self.saved_hash = hashlib.sha256(raw).hexdigest()

    def discard(self):
        self.saved, self.saved_hash = read(self.project) if self.project else (deepcopy(EMPTY), None)
        self.value = deepcopy(self.saved)

    def _skill(self, identity):
        return next((s for s in self.value['skills'] if s['id'] == identity), None)

    def list_rows(self):
        old = {s['id']: s for s in self.saved['skills']}
        return [{'table': TABLE, 'id': s['id'], 'name': s['name'],
                 'values': {**s, 'iconId': -1 if s['iconId'] is None else s['iconId']},
                 'display': {'iconId': 'None' if s['iconId'] is None else str(s['iconId'])},
                 'created': s['id'] not in old, 'modified': old.get(s['id']) != s}
                for s in self.value['skills']]

    def read_row(self, identity):
        skill = self._skill(identity)
        if skill is None:
            raise ValueError('Choose an existing Ash of War')
        fields = []
        for key, label, kind, maximum in [('description', 'Description', 'longtext', 2000),
                                         ('iconId', 'Icon', 'number', 65535),
                                         ('fpCost', 'FP cost', 'number', 65535),
                                         ('staminaCost', 'Stamina cost', 'number', 65535)]:
            value = -1 if key == 'iconId' and skill[key] is None else skill[key]
            fields.append({'key': key, 'label': label, 'group': 'Skill', 'type': kind,
                           'dtype': 's32' if kind == 'number' else 'text', 'editable': True,
                           'value': value, 'minimum': -1 if key == 'iconId' else 0,
                           'maximum': maximum, 'maxLength': maximum, 'enum': {},
                           'description': 'Choose a picture from the icon gallery, or clear it to leave the skill without an icon.' if key == 'iconId' else '',
                           **({'emptyValue': -1} if key == 'iconId' else {})})
        links = [{'field': 'iconId', 'kind': 'asset', 'tab': 'textures', 'id': skill['iconId'],
                  'name': 'No icon' if skill['iconId'] is None else 'Skill icon'}]
        return {'table': TABLE, 'id': identity, 'name': skill['name'], 'fields': fields, 'recordLinks': links,
                'help': 'Define the skill shown for each assigned weapon. These records do not implement a combat action.'}

    def add(self, source=None):
        self.editable()
        if len(self.value['skills']) >= 4096:
            raise ValueError('The skill catalog is full')
        identity = max((s['id'] for s in self.value['skills']), default=0) + 1
        integer(identity, 1, 2147483647, 'Skill ID')
        skill = deepcopy(self._skill(source)) if source is not None else None
        if source is not None and skill is None:
            raise ValueError('Choose a skill to duplicate')
        skill = skill or {'name': 'New Ash of War', 'description': '', 'iconId': None, 'fpCost': 0, 'staminaCost': 0}
        skill['id'] = identity
        if source is not None:
            skill['name'] = skill['name'][:73] + ' (copy)'
        self.value['skills'].append(skill)
        return self.read_row(identity)

    def edit(self, identity, key, value):
        self.editable()
        skill = self._skill(identity)
        if skill is None or key not in KEYS - {'id'}:
            raise ValueError('Choose an editable skill field')
        candidate = deepcopy(self.value)
        target = next(s for s in candidate['skills'] if s['id'] == identity)
        target[key] = None if key == 'iconId' and value == -1 else value
        self.value = validate(candidate)
        return self.read_row(identity)

    def remove(self, identity):
        self.editable()
        if self._skill(identity) is None:
            raise ValueError('Choose an existing Ash of War')
        if any(a['skillId'] == identity for a in self.value['assignments']):
            raise ValueError('Remove this skill from its weapons before deleting it')
        self.value['skills'] = [s for s in self.value['skills'] if s['id'] != identity]
        return identity

    def assignment(self, weapon):
        return next((a['skillId'] for a in self.value['assignments'] if a['weaponId'] == weapon), 0)

    def icon_id(self, identity):
        skill = self._skill(identity)
        return None if skill is None else skill['iconId']

    def assign(self, weapon, skill, weapon_ids):
        self.editable()
        integer(weapon, 0, 2147483647, 'Weapon ID')
        if weapon not in weapon_ids:
            raise ValueError('Choose a weapon the game knows')
        integer(skill, 0, 2147483647, 'Skill')
        candidate = deepcopy(self.value)
        candidate['assignments'] = [a for a in candidate['assignments'] if a['weaponId'] != weapon]
        if skill:
            candidate['assignments'].append({'weaponId': weapon, 'skillId': skill})
        self.value = validate(candidate, weapon_ids)

    def decorate_weapon(self, row):
        if any(f['key'] == 'ashOfWar' for f in row['fields']):
            return row
        skill_id = self.assignment(row['id'])
        choices = {'0': 'None', **{str(s['id']): s['name'] for s in self.value['skills']}}
        row['fields'].append({'key': 'ashOfWar', 'label': 'Ash of War', 'group': 'Use behavior',
                              'value': skill_id, 'type': 'enum', 'dtype': 's32', 'editable': True,
                              'minimum': 0, 'maximum': 2147483647, 'enum': choices,
                              'description': 'The skill assigned to this exact weapon variant. None leaves it unassigned.'})
        if skill_id:
            row.setdefault('recordLinks', []).append({'field': 'ashOfWar', 'kind': 'catalog',
                'tab': 'items', 'sub': TAB, 'table': TABLE, 'id': skill_id, 'name': choices[str(skill_id)]})
        return row
