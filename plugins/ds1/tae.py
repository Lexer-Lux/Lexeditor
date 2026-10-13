"""Remastered animation events (TAE1), edited with byte preservation.

Field edits rewrite fixed-size values in place. Added and removed events
relocate one animation's event table and timestamp pool to appended bytes;
nothing else in the file moves, and the old regions stay as unreachable
bytes.

Container layout: Apache-2.0 SoulsTemplates TAE3 templates by TKGP
(see credits.md), translated to the 32-bit DS1 form and verified
against every .tae in every readable character binder: 270 files,
15161 animations, about 200000 events. Event-type meanings:
soulsmodding wiki format:tae (CC BY-SA, paraphrased with
attribution) confirmed against measured value distributions;
DSAnimStudio's DS1 template served as a read-only cross-check and
none of its text is reused. No template code is redistributed.

Every event carries start and end timestamps in seconds. Timestamps
live in one shared pool per animation: several events often point at
the same second, and editing it moves them together. Event data is
one type ID, one pointer to its own parameters, then the parameters.
Parameter layouts below are proven for DS1; anything else stays
read-only, including whole event types whose layout is unconfirmed.
"""
import math
import struct
from pathlib import Path

from .formats import FormatError

CHR_DIR = Path("chr")
MAX_BINDER = 64 * 1024 * 1024
VERSION = 0x1000B
MAX_FILE = 8 * 1024 * 1024
HEADER_SIZE = 64
ANIM_SIZE = 28
EVENT_SIZE = 12
KINDS = {'s32': ('i', -(2 ** 31), 2 ** 31 - 1), 'u8': ('B', 0, 255),
         's16': ('h', -(2 ** 15), 2 ** 15 - 1), 'u16': ('H', 0, 65535),
         'f32': ('f', None, None)}
# Widths shown as control bounds; whole-width integers never show a range.
BOUNDED = frozenset({'u8', 'u16'})
# Attack meanings: soulsmodding wiki format:tae, all five observed.
ATTACK_TYPES = {0: 'Standard', 1: "Infested Ghoul jump slash",
                2: 'Forward + R1', 62: 'Plunging attack', 64: 'Parry'}


class TaeError(FormatError):
    """An animation file Lexeditor cannot safely read."""


# Event layouts: type -> (size, label, fields). Each field is
# (key, label, kind, offset, editable, description); offsets count
# from the event data start and parameters begin at +8.
EVENT_TYPES = {
    0: (20, 'Action flag', (
        ('flag', 'Action', 's32', 8, True,
         'Which action runs while the event lasts. 3 guards using the extra ID, '
         '23 lets the AI chain attacks, 49 blocks lock-on.'),
        ('argA', 'Extra value', 'f32', 12, True,
         'Extra value for some actions. Almost always 0.'),
        ('argB', 'Extra ID', 's32', 16, True,
         'Extra ID for some actions, such as the guard behavior for action 3. '
         'Most vanilla events use -1.'),
    )),
    1: (20, 'Attack', (
        ('attackType', 'Attack type', 's32', 8, True,
         'Which attack this behaves as. Only the Ghoul jump slash is unconfirmed.'),
        ('attackIndex', 'Attack slot', 's32', 12, True,
         'Which attack slot this behavior uses. Vanilla uses 0 to 7.'),
        ('judge', 'Behavior key', 's32', 16, True,
         'Behavior lookup key. It pairs with the user behavior variation, '
         'so it cannot be checked here.'),
    )),
    2: (24, 'Projectile', (
        ('dummy', 'Origin node', 's32', 8, True,
         'Skeleton node the projectile leaves from, by ID.'),
        ('judge', 'Behavior key', 's32', 16, True,
         'Behavior lookup key. It pairs with the user behavior variation, '
         'so it cannot be checked here.'),
    )),
    5: (16, 'Common behavior', (
        ('attackIndex', 'Attack slot', 's32', 8, True,
         'Which attack slot this behavior uses. Vanilla uses 0 to 3.'),
        ('judge', 'Behavior key', 's32', 12, True,
         'Behavior lookup key. It pairs with the user behavior variation, '
         'so it cannot be checked here.'),
    )),
    24: (24, 'Queue animation', (
        ('destAnim', 'Next animation', 's32', 12, True,
         'Animation to switch to, by ID.'),
        ('transAnim', 'Bridge animation', 's32', 16, True,
         'Animation played while switching, by ID.'),
    )),
    32: (12, 'Weapon style', (
        ('style', 'Style', 's32', 8, True,
         'Weapon style. Vanilla uses 1, 2 and 3.'),
    )),
    33: (12, 'Switch weapon', (
        ('slot', 'Weapon slot', 's32', 8, True,
         'Weapon slot to switch to. Vanilla uses 0 to 3.'),
    )),
    64: (16, 'Cast magic', (
        ('dummy', 'Origin node', 's32', 8, True,
         'Skeleton node the magic leaves from, by ID.'),
    )),
    65: (12, 'Use item', (
        ('dummy', 'Origin node', 's32', 8, True,
         'Skeleton node the item is used from, by ID.'),
    )),
    66: (12, 'Add effect', (
        ('effect', 'Effect', 's32', 8, True,
         'Special effect applied while the event lasts, by ID.'),
    )),
    67: (12, 'Add effect', (
        ('effect', 'Effect', 's32', 8, True,
         'Special effect applied while the event lasts, by ID.'),
    )),
    96: (20, 'Spawn effect', (
        ('effectId', 'Effect', 's32', 8, True, 'Visual effect to spawn, by ID.'),
        ('dummy', 'Origin node', 's32', 12, True,
         'Skeleton node the effect spawns at, by ID. -1 means none.'),
        ('slot', 'Slot', 's32', 16, True,
         'Effect slot. Vanilla uses -1 to 23.'),
    )),
    99: (20, 'Spawn effect', (
        ('effectId', 'Effect', 's32', 8, True, 'Visual effect to spawn, by ID.'),
        ('dummy', 'Origin node', 's32', 12, True,
         'Skeleton node the effect spawns at, by ID. -1 means none.'),
        ('slot', 'Slot', 's32', 16, True,
         'Effect slot. Vanilla uses -1 to 23.'),
    )),
    100: (20, 'Spawn effect', (
        ('effectId', 'Effect', 's32', 8, True, 'Visual effect to spawn, by ID.'),
        ('dummy', 'Origin node', 's32', 12, True,
         'Skeleton node the effect spawns at, by ID. -1 means none.'),
        ('slot', 'Slot', 's32', 16, True,
         'Effect slot. Vanilla uses -1 to 23.'),
    )),
    101: (12, 'Spawn effect', (
        ('effectId', 'Effect', 's32', 8, True, 'Visual effect to spawn, by ID.'),
    )),
    104: (20, 'Spawn effect', (
        ('effectId', 'Effect', 's32', 8, True, 'Visual effect to spawn, by ID.'),
        ('dummy', 'Origin node', 's32', 12, True,
         'Skeleton node the effect spawns at, by ID. -1 means none.'),
        ('slot', 'Slot', 's32', 16, True,
         'Effect slot. Vanilla uses -1 to 23.'),
    )),
    108: (20, 'Spawn effect', (
        ('effectId', 'Effect', 's32', 8, True, 'Visual effect to spawn, by ID.'),
        ('dummy', 'Origin node', 's32', 12, True,
         'Skeleton node the effect spawns at, by ID. -1 means none.'),
        ('slot', 'Slot', 's32', 16, True,
         'Effect slot. Vanilla uses -1 to 23.'),
    )),
    109: (20, 'Spawn effect', (
        ('effectId', 'Effect', 's32', 8, True, 'Visual effect to spawn, by ID.'),
        ('dummy', 'Origin node', 's32', 12, True,
         'Skeleton node the effect spawns at, by ID. -1 means none.'),
        ('slot', 'Slot', 's32', 16, True,
         'Effect slot. Vanilla uses -1 to 23.'),
    )),
    110: (12, 'Spawn effect', (
        ('effectId', 'Effect', 's32', 8, True, 'Visual effect to spawn, by ID.'),
    )),
    112: (16, 'Spawn floor effect', (
        ('effectId', 'Effect', 's32', 8, True, 'Visual effect to spawn, by ID.'),
        ('dummy', 'Origin node', 's32', 12, True,
         'Skeleton node the effect spawns at, by ID. -1 means none.'),
    )),
    114: (20, 'Spawn effect', (
        ('effectId', 'Effect', 's32', 8, True, 'Visual effect to spawn, by ID.'),
        ('dummy', 'Origin node', 's16', 10, True,
         'Skeleton node the effect spawns at, by ID.'),
        ('slot', 'Slot', 's32', 16, True,
         'Effect slot. -1 means none.'),
    )),
    115: (20, 'Spawn effect', (
        ('effectId', 'Effect', 's32', 8, True, 'Visual effect to spawn, by ID.'),
        ('dummy', 'Origin node', 's16', 10, True,
         'Skeleton node the effect spawns at, by ID.'),
        ('slot', 'Slot', 's32', 16, True,
         'Effect slot.'),
    )),
    116: (20, 'Spawn effect', (
        ('effectId', 'Effect', 's32', 8, True, 'Visual effect to spawn, by ID.'),
        ('dummy', 'Origin node', 's32', 12, True,
         'Skeleton node the effect spawns at, by ID. -1 means none.'),
        ('slot', 'Slot', 's32', 16, True,
         'Effect slot. Vanilla uses -1 to 23.'),
    )),
    118: (20, 'Spawn blade effect', (
        ('effectId', 'Effect', 's32', 8, True, 'Visual effect to spawn, by ID.'),
        ('bladeBase', 'Blade base node', 's16', 12, True,
         'Skeleton node at the blade base, by ID.'),
        ('bladeTip', 'Blade tip node', 's16', 14, True,
         'Skeleton node at the blade tip, by ID.'),
        ('slot', 'Slot', 's16', 16, True, 'Effect slot.'),
    )),
    119: (20, 'Spawn body effect', (
        ('effectId', 'Effect', 's32', 8, True, 'Visual effect to spawn, by ID.'),
        ('dummy', 'Origin node', 's16', 12, True,
         'Skeleton node the effect spawns at, by ID.'),
    )),
    120: (32, 'Spawn ghost effect', (
        ('effectMain', 'Living effect', 's32', 8, True,
         'Visual effect while living, by ID.'),
        ('effectGrey', 'Grey ghost effect', 's32', 12, True,
         'Visual effect as a grey ghost, by ID.'),
        ('effectWhite', 'White ghost effect', 's32', 16, True,
         'Visual effect as a white ghost, by ID.'),
        ('effectBlack', 'Black ghost effect', 's32', 20, True,
         'Visual effect as a black ghost, by ID.'),
        ('dummy', 'Origin node', 's32', 24, True,
         'Skeleton node the effect spawns at, by ID. -1 means none.'),
        ('slot', 'Slot', 's32', 28, True,
         'Effect slot. Vanilla uses -1, 1, 10 and 11.'),
    )),
    121: (16, 'Spawn effect', (
        ('effectId', 'Effect', 's32', 8, True, 'Visual effect to spawn, by ID.'),
        ('dummy', 'Origin node', 's16', 12, True,
         'Skeleton node the effect spawns at, by ID.'),
    )),
    128: (16, 'Play sound', (
        ('soundType', 'Sound bank', 's32', 8, True,
         'Which sound bank plays. Vanilla uses 1, 5, 7, 8 and 9.'),
        ('soundId', 'Sound', 's32', 12, True, 'Sound to play, by ID.'),
    )),
    129: (24, 'Play sound', (
        ('soundType', 'Sound bank', 's32', 8, True,
         'Which sound bank plays. Vanilla uses 1, 3, 5 and 8.'),
        ('soundId', 'Sound', 's32', 12, True, 'Sound to play, by ID.'),
        ('dummy', 'Origin node', 's32', 16, True,
         'Skeleton node the sound plays at, by ID. -1 means none.'),
        ('slot', 'Slot', 's32', 20, True,
         'Sound slot. Vanilla uses -1 to 99.'),
    )),
    130: (24, 'Play sound', (
        ('soundType', 'Sound bank', 's32', 8, True,
         'Which sound bank plays. Vanilla always uses 1.'),
        ('soundId', 'Sound', 's32', 12, True, 'Sound to play, by ID.'),
        ('dummy', 'Origin node', 's32', 16, True,
         'Skeleton node the sound plays at, by ID. -1 means none.'),
        ('slot', 'Slot', 's32', 20, True,
         'Sound slot. Vanilla always uses -1.'),
    )),
    144: (20, 'Camera shake', (
        ('shakeId', 'Shake', 's16', 8, True, 'Camera shake to play, by ID.'),
        ('dummy', 'Origin node', 'u16', 10, True,
         'Skeleton node the shake centers on, by ID.'),
        ('falloffStart', 'Falloff start', 'f32', 12, True,
         'Distance where the shake starts fading.'),
        ('falloffEnd', 'Falloff end', 'f32', 16, True,
         'Distance where the shake is gone.'),
    )),
    145: (12, 'Camera shake', (
        ('shakeId', 'Shake', 's16', 8, True, 'Camera shake to play, by ID.'),
    )),
    193: (16, 'Opacity', (
        ('opacityStart', 'Start opacity', 'f32', 8, True,
         'Opacity when the event starts. 1 is solid, 0 is invisible.'),
        ('opacityEnd', 'End opacity', 'f32', 12, True,
         'Opacity when the event ends. The character returns to its default opacity after.'),
    )),
    224: (12, 'Turn speed', (
        ('speed', 'Turn speed', 'f32', 8, True,
         'Turn speed while the event lasts, said to be degrees per second.'),
    )),
    225: (12, 'Stamina recovery', (
        ('rate', 'Recovery rate', 'u8', 8, True,
         'Stamina recovery while the event lasts, as a percent. 100 is full speed.'),
    )),
    226: (12, 'Knockback', (
        ('percent', 'Strength', 'u8', 8, True,
         'Knockback strength while the event lasts, as a percent.'),
    )),
    229: (12, 'AI sound', (
        ('soundId', 'Sound', 's32', 8, True,
         'Sound nearby AI can hear, by ID.'),
    )),
    231: (12, 'Event state', (
        ('requestId', 'Request', 's32', 8, True,
         'Event-state request to send, by ID.'),
    )),
    232: (12, 'Vertical aim', (
        ('upLimit', 'Aim-up limit', 'u8', 8, True,
         'Highest angle the body can aim up, in degrees.'),
        ('downLimit', 'Aim-down limit', 'u8', 9, True,
         'Lowest angle the body can aim down, in degrees.'),
        ('upThreshold', 'Aim-up start', 'u8', 10, True,
         'Camera angle where upward aiming starts, in degrees.'),
        ('downThreshold', 'Aim-down start', 'u8', 11, True,
         'Camera angle where downward aiming starts, in degrees.'),
    )),
    236: (20, 'Root motion', (
        ('reductionStart', 'Start reduction', 'f32', 8, True,
         'Root-motion setting when the event starts. Vanilla uses 0.4 to 1.'),
        ('reductionEnd', 'End reduction', 'f32', 12, True,
         'Root-motion setting when the event ends. Vanilla uses 0.5 to 1.'),
    )),
    300: (24, 'Action gradient', (
        ('gradStart', 'Start value', 'f32', 12, True,
         'Gradient value when the event starts.'),
        ('gradEnd', 'End value', 'f32', 16, True,
         'Gradient value when the event ends.'),
    )),
    302: (12, 'Add effect', (
        ('effect', 'Effect', 's32', 8, True,
         'Special effect applied while the event lasts, by ID.'),
    )),
    303: (12, 'Play animation', (
        ('animId', 'Animation', 's32', 8, True,
         'Animation to play, by ID.'),
    )),
    304: (16, 'Throw attack', (
        ('judge', 'Behavior key', 's32', 12, True,
         'Behavior lookup key. It pairs with the user behavior variation, '
         'so it cannot be checked here.'),
    )),
    306: (20, 'Physics dampen', (
        ('dampStart', 'Start dampening', 'f32', 8, True,
         'Dampening when the event starts, from 0 to 1.'),
        ('dampEnd', 'End dampening', 'f32', 12, True,
         'Dampening when the event ends, from 0 to 1.'),
        ('mask', 'Mask', 's32', 16, True,
         'Which parts dampen, as a bit mask. Vanilla uses 1, 247 and 255.'),
    )),
    307: (20, 'Player behavior', (
        ('pcType', 'Behavior type', 's32', 12, True,
         'Player behavior type. Vanilla uses 2, 4, 8, 16, 32, 64 and 128.'),
        ('judge', 'Behavior key', 's32', 16, True,
         'Behavior lookup key. It pairs with the user behavior variation, '
         'so it cannot be checked here.'),
    )),
    401: (12, 'Add effect', (
        ('effect', 'Effect', 's32', 8, True,
         'Special effect applied while the event lasts, by ID.'),
    )),
    500: (12, 'Ignore hits', (
        ('maskId', 'Mask', 'u8', 8, True,
         'Which body parts ignore hits. Vanilla uses 1 and 9.'),
    )),
}


def _wstring(data, offset, what):
    """A stored wide string. Display-only names fall back instead of
    failing the file; offsets outside the file fail it."""
    if not 0 <= offset <= len(data) - 2:
        raise TaeError(f'{what} offset is invalid')
    end = offset
    while end + 2 <= len(data) and data[end:end + 2] != b'\0\0':
        end += 2
    if end + 2 > len(data):
        raise TaeError(f'{what} is not terminated')
    try:
        return bytes(data[offset:end]).decode('utf-16-le')
    except UnicodeError:
        return ''


class TaeDocument:
    """One .tae file's animation events. Field edits rewrite fixed-size
    values in place; added and removed events append a relocated table
    and pool. Everything else is preserved byte for byte."""

    def __init__(self, source, name=''):
        if len(source) > MAX_FILE:
            raise TaeError('The animation file is too large')
        self.original = bytes(source)
        self.plain = bytearray(source)
        self.name = name
        self.anims = []
        self._slot_users = {}
        self.dirty = set()
        self.removed = []
        data = self.plain
        if len(data) < HEADER_SIZE or data[:4] != b'TAE ' or data[4] != 0 or data[7] != 0:
            raise TaeError('Expected a Remastered animation file')
        version, size, off40, unk14, off50, off70 = struct.unpack_from('<6I', data, 8)
        if version != VERSION:
            raise TaeError('Unsupported animation version')
        if size != len(data):
            raise TaeError('Animation length mismatch')
        if (off40, unk14, off50, off70) != (0x40, 1, 0x50, 0x70):
            raise TaeError('Unsupported animation header')
        file_id, anim_count, anims_off, groups_off = struct.unpack_from('<4I', data, 80)
        off90, count2, _first = struct.unpack_from('<3I', data, 96)
        if off90 != 0x90 or count2 != anim_count:
            raise TaeError('Unsupported animation header')
        if not (0 < anim_count <= 10000 and anims_off + anim_count * 8 <= len(data)):
            raise TaeError('Animation list is invalid')
        if not groups_off + 8 <= len(data):
            raise TaeError('Animation groups are invalid')
        group_count, groups_at = struct.unpack_from('<2I', data, groups_off)
        if not groups_at + group_count * 12 <= len(data):
            raise TaeError('Animation groups are invalid')
        for index in range(anim_count):
            anim_id, anim_off = struct.unpack_from('<2I', data, anims_off + index * 8)
            self._read_anim(anim_id, anim_off, index)

    def _read_anim(self, anim_id, anim_off, index):
        data = self.plain
        if not 0 <= anim_off <= len(data) - ANIM_SIZE:
            raise TaeError('An animation entry is out of bounds')
        ev_n, ev_off, g_n, g_off, t_n, t_off, f_off = struct.unpack_from('<7I', data, anim_off)
        if (g_n, g_off) != (0, 0):
            raise TaeError('Event groups are not supported')
        if t_off + t_n * 4 > len(data) or ev_off + ev_n * EVENT_SIZE > len(data):
            raise TaeError('An animation entry is out of bounds')
        if not f_off + 24 <= len(data):
            raise TaeError('An animation entry is out of bounds')
        ref, fnoo, fno = struct.unpack_from('<3I', data, f_off)
        if fnoo != f_off + 8:
            raise TaeError('An animation entry is invalid')
        # A name offset at end of file means the animation has no name.
        anim_name = _wstring(data, fno, 'An animation name') if fno not in (0, len(data)) else ''
        events = []
        for number in range(ev_n):
            base = ev_off + number * EVENT_SIZE
            start_off, end_off, data_off = struct.unpack_from('<3I', data, base)
            if not t_off <= start_off < t_off + t_n * 4 or (start_off - t_off) % 4:
                raise TaeError('An event timestamp is invalid')
            if not t_off <= end_off < t_off + t_n * 4 or (end_off - t_off) % 4:
                raise TaeError('An event timestamp is invalid')
            if not data_off + 8 <= len(data):
                raise TaeError('An event is out of bounds')
            etype, param_off = struct.unpack_from('<iI', data, data_off)
            if param_off == 0:
                empty = True
            elif param_off != data_off + 8:
                raise TaeError('An event layout is not supported')
            else:
                empty = False
            known = EVENT_TYPES.get(etype)
            if not empty and known is not None and data_off + known[0] > len(data):
                raise TaeError('An event is out of bounds')
            events.append({'index': number, 'type': etype, 'start_off': start_off,
                           'end_off': end_off, 'data_off': data_off, 'tight': False,
                           'empty': empty, 'vanilla_index': number})
            for slot, field in ((start_off, 'start'), (end_off, 'end')):
                self._slot_users.setdefault(slot, []).append((index, number, field))
        self.anims.append({'index': index, 'id': anim_id,
                           'name': anim_name or f'animation {anim_id}',
                           'reference': ref, 'offset': anim_off,
                           'pool': [t_off + slot * 4 for slot in range(t_n)],
                           'events': events})
        self._mark_tight(self.anims[-1])

    def _mark_tight(self, anim):
        """Flag events whose data has no room for its documented size."""
        datas = sorted(event['data_off'] for event in anim['events'])
        for event in anim['events']:
            if event['empty']:
                size = 8
            else:
                size = (EVENT_TYPES[event['type']][0] if event['type'] in EVENT_TYPES else 8)
            after = [d for d in datas if d > event['data_off']]
            event['tight'] = bool(after and after[0] - event['data_off'] < size)

    def list_anims(self):
        """Animations in file order with their event counts."""
        return [{'index': anim['index'], 'id': anim['id'], 'name': anim['name'],
                 'events': len(anim['events'])} for anim in self.anims]

    def list_events(self, anim_index):
        """An animation's events in file order with timestamps."""
        anim = self._anim(anim_index)
        result = []
        for event in anim['events']:
            known = EVENT_TYPES.get(event['type'])
            result.append({'index': event['index'], 'type': event['type'],
                           'label': known[1] if known else f"Unknown event {event['type']}",
                           'start': self._time(event['start_off']),
                           'end': self._time(event['end_off'])})
        return result

    @property
    def dirty_count(self):
        return len(self.dirty) + len(self.removed)

    def _anim(self, anim_index):
        if (type(anim_index) is not int or isinstance(anim_index, bool)
                or not 0 <= anim_index < len(self.anims)):
            raise TaeError('Select an animation from this file')
        return self.anims[anim_index]

    def _event(self, anim_index, event_index):
        anim = self._anim(anim_index)
        if (type(event_index) is not int or isinstance(event_index, bool)
                or not 0 <= event_index < len(anim['events'])):
            raise TaeError('Select an event from this animation')
        return anim, anim['events'][event_index]

    def _time(self, offset):
        return struct.unpack_from('<f', self.plain, offset)[0]

    def _field_value(self, event, kind, offset):
        code, _, _ = KINDS[kind]
        return struct.unpack_from('<' + code, self.plain, event['data_off'] + offset)[0]

    def _field_original(self, event, kind, offset):
        code, _, _ = KINDS[kind]
        at = event['data_off'] + offset
        if at + struct.calcsize(code) > len(self.original):
            return None
        return struct.unpack_from('<' + code, self.original, at)[0]

    def _time_field(self, event, field, offset):
        users = self._slot_users.get(offset, [])
        others = len(users) - 1
        if field == 'start':
            description = 'When the event starts, in seconds.'
        else:
            description = 'When the event ends, in seconds.'
        if others > 0:
            description += (f' {others} other event shares this timestamp and changes too.'
                            if others == 1 else
                            f' {others} other events share this timestamp and change too.')
        return {'key': field, 'label': 'Start' if field == 'start' else 'End',
                'description': description, 'group': 'Timing', 'dtype': 'f32',
                'value': self._time(offset), 'type': 'number',
                'minimum': None, 'maximum': None, 'enum': {}, 'editable': True,
                'vanilla': (struct.unpack_from('<f', self.original, offset)[0]
                            if offset + 4 <= len(self.original) else None),
                'sliderMin': None, 'sliderMax': None, 'shared': others}

    def read_event(self, anim_index, event_index):
        """One event's editable fields with vanilla values."""
        anim, event = self._event(anim_index, event_index)
        known = EVENT_TYPES.get(event['type'])
        group = known[1] if known else f"Unknown event {event['type']}"
        fields = [self._time_field(event, 'start', event['start_off']),
                  self._time_field(event, 'end', event['end_off'])]
        if known is not None and not event['tight'] and not event['empty']:
            for key, label, kind, offset, _editable, description in known[2]:
                _, minimum, maximum = KINDS[kind]
                if kind not in BOUNDED:
                    minimum, maximum = None, None
                fields.append({'key': key, 'label': label, 'description': description,
                               'group': group, 'dtype': kind,
                               'value': self._field_value(event, kind, offset), 'type': 'number',
                               'minimum': minimum, 'maximum': maximum, 'enum': {}, 'editable': True,
                               'vanilla': self._field_original(event, kind, offset),
                               'sliderMin': None, 'sliderMax': None})
        return {'anim': anim['id'], 'animName': anim['name'], 'index': event['index'],
                'type': event['type'], 'label': group, 'fields': fields,
                'vanillaIndex': event['vanilla_index']}

    @staticmethod
    def _time_payload(value):
        if type(value) not in (int, float) or isinstance(value, bool) or not math.isfinite(value):
            raise TaeError('Enter a finite number of seconds')
        try:
            return struct.pack('<f', value)
        except OverflowError as error:
            raise TaeError('Enter a finite number of seconds') from error

    @staticmethod
    def _checked_field(etype, field, value, speffect_ids, original):
        """A parameter value as stored bytes. original exempts an effect
        being restored; added events pass None and validate strictly."""
        spec = next((entry for entry in EVENT_TYPES[etype][2] if entry[0] == field), None)
        if spec is None:
            raise TaeError('Unknown event field')
        _key, _label, kind, offset, _editable, _description = spec
        if kind == 'f32':
            if type(value) not in (int, float) or isinstance(value, bool) or not math.isfinite(value):
                raise TaeError('Enter a finite number')
            try:
                payload = struct.pack('<f', value)
            except OverflowError as error:
                raise TaeError('Enter a finite number') from error
        else:
            _code, minimum, maximum = KINDS[kind]
            if type(value) is not int or isinstance(value, bool) or not minimum <= value <= maximum:
                raise TaeError('Enter a whole number')
            if etype == 1 and field == 'attackType' and value not in ATTACK_TYPES:
                raise TaeError('Choose a documented attack type')
            if field == 'effect' and speffect_ids is not None and value not in speffect_ids and value != original:
                raise TaeError('Choose an effect the game knows')
            payload = struct.pack('<' + _code, value)
        return kind, offset, payload

    def edit(self, anim_index, event_index, field, value, speffect_ids=None):
        """Change one event field in place. speffect_ids, when given, is
        the set of SpEffectParam row IDs an effect field may point at."""
        anim, event = self._event(anim_index, event_index)
        if field in ('start', 'end'):
            payload = self._time_payload(value)
            offset = event['start_off'] if field == 'start' else event['end_off']
            self.plain[offset:offset + 4] = payload
            for user in self._slot_users.get(offset, []):
                key = (user[0], user[1], user[2])
                slot = self._user_slot(user)
                if slot + 4 > len(self.original):
                    self.dirty.add(key)
                elif struct.unpack_from('<f', self.plain, slot)[0] == struct.unpack_from(
                        '<f', self.original, slot)[0]:
                    self.dirty.discard(key)
                else:
                    self.dirty.add(key)
            return self.read_event(anim_index, event_index)
        known = EVENT_TYPES.get(event['type'])
        spec = next((entry for entry in known[2] if entry[0] == field), None) if known else None
        if spec is None or event['tight'] or event['empty']:
            raise TaeError('This event field is protected')
        original = self._field_original(event, spec[2], spec[3]) if field == 'effect' else None
        kind, offset, payload = self._checked_field(event['type'], field, value, speffect_ids, original)
        start = event['data_off'] + offset
        self.plain[start:start + len(payload)] = payload
        key = (anim['index'], event['index'], field)
        if self._field_value(event, kind, offset) == self._field_original(event, kind, offset):
            self.dirty.discard(key)
        else:
            self.dirty.add(key)
        return self.read_event(anim_index, event_index)

    def _user_slot(self, user):
        anim_index, event_index, field = user
        event = self.anims[anim_index]['events'][event_index]
        return event['start_off'] if field == 'start' else event['end_off']

    def _relocate(self, anim_off, entries, pool, extra):
        """Append a fresh event table, timestamp pool and extra data for
        one animation; point its entry at them. A None data offset means
        the appended extra block. Returns the table, pool and extra
        offsets. Nothing else in the file moves."""
        base = len(self.plain) + (-len(self.plain) % 4)
        ev_off = base
        t_off = ev_off + len(entries) * EVENT_SIZE
        data_base = t_off + len(pool) * 4
        blob = bytearray(b'\x00' * (ev_off - len(self.plain)))
        for start, end, data_off in entries:
            blob += struct.pack('<3I', t_off + start * 4, t_off + end * 4,
                                data_base if data_off is None else data_off)
        for tick in pool:
            blob += struct.pack('<f', tick)
        extra = bytearray(extra)
        if extra:
            struct.pack_into('<I', extra, 4, data_base + 8)
            blob += extra
        if len(self.plain) + len(blob) > MAX_FILE:
            raise TaeError('The animation file is too large')
        self.plain += blob
        struct.pack_into('<2I', self.plain, anim_off, len(entries), ev_off)
        struct.pack_into('<2I', self.plain, anim_off + 16, len(pool), t_off)
        return ev_off, t_off, data_base

    def _refresh_users(self, anim_index):
        """Rebuild one animation's timestamp sharing after a relocation."""
        anim = self.anims[anim_index]
        self._slot_users = {slot: [user for user in users if user[0] != anim_index]
                            for slot, users in self._slot_users.items()}
        for number, event in enumerate(anim['events']):
            for slot, field in ((event['start_off'], 'start'), (event['end_off'], 'end')):
                self._slot_users.setdefault(slot, []).append((anim_index, number, field))
        self._mark_tight(anim)

    def add_event(self, anim_index, etype, start, end, values=None, speffect_ids=None):
        """Append an event of a documented type with fresh timestamps.
        values names parameter fields; the rest start at 0. Returns the
        new event's index."""
        anim = self._anim(anim_index)
        if type(etype) is not int or isinstance(etype, bool) or etype not in EVENT_TYPES:
            raise TaeError('Choose a documented event type')
        self._time_payload(start)
        self._time_payload(end)
        size, _label, fields = EVENT_TYPES[etype]
        given = dict(values or {})
        for key in given:
            if key not in {entry[0] for entry in fields}:
                raise TaeError('Unknown event field')
        blob = bytearray(size)
        struct.pack_into('<i', blob, 0, etype)
        for key, _label, _kind, offset, _editable, _description in fields:
            if key not in given:
                continue
            _kind, _offset, payload = self._checked_field(etype, key, given[key], speffect_ids, None)
            blob[offset:offset + len(payload)] = payload
        pool = [self._time(slot) for slot in anim['pool']] + [float(start), float(end)]
        entries = [(anim['pool'].index(event['start_off']), anim['pool'].index(event['end_off']),
                    event['data_off']) for event in anim['events']]
        entries.append((len(pool) - 2, len(pool) - 1, None))
        _ev_off, t_off, data_base = self._relocate(anim['offset'], entries, pool, blob)
        anim['pool'] = [t_off + slot * 4 for slot in range(len(pool))]
        for event, (slot, stop, _data) in zip(anim['events'], entries):
            event['start_off'] = t_off + slot * 4
            event['end_off'] = t_off + stop * 4
        event = {'index': len(anim['events']), 'type': etype,
                 'start_off': t_off + (len(pool) - 2) * 4, 'end_off': t_off + (len(pool) - 1) * 4,
                 'data_off': data_base, 'tight': False, 'empty': False, 'vanilla_index': None}
        anim['events'].append(event)
        self._refresh_users(anim_index)
        for key in ('start', 'end'):
            self.dirty.add((anim_index, event['index'], key))
        for key, _label, _kind, _offset, _editable, _description in fields:
            self.dirty.add((anim_index, event['index'], key))
        return event['index']

    def remove_event(self, anim_index, event_index):
        """Delete an event. Later events keep their values and vanilla
        links; only their indices shift down."""
        anim, event = self._event(anim_index, event_index)
        if event['vanilla_index'] is not None:
            known = EVENT_TYPES.get(event['type'])
            self.removed.append({'anim': anim['index'], 'animName': anim['name'],
                                 'event': event['vanilla_index'],
                                 'label': known[1] if known else f"Unknown event {event['type']}",
                                 'start': self._time(event['start_off']),
                                 'end': self._time(event['end_off'])})
        survivors = [entry for entry in anim['events'] if entry is not event]
        pool = [self._time(slot) for slot in anim['pool']]
        entries = [(anim['pool'].index(entry['start_off']), anim['pool'].index(entry['end_off']),
                    entry['data_off']) for entry in survivors]
        _ev_off, t_off, _data = self._relocate(anim['offset'], entries, pool, b'')
        anim['pool'] = [t_off + slot * 4 for slot in range(len(pool))]
        for number, entry in enumerate(survivors):
            entry['index'] = number
            entry['start_off'] = t_off + entries[number][0] * 4
            entry['end_off'] = t_off + entries[number][1] * 4
        anim['events'] = survivors
        self._refresh_users(anim_index)
        self.dirty = {(anim_id, number - 1 if anim_id == anim_index and number > event_index else number, field)
                      for anim_id, number, field in self.dirty
                      if not (anim_id == anim_index and number == event_index)}

    def export(self):
        if bytes(self.plain) == self.original:
            return self.original
        out = bytearray(self.plain)
        struct.pack_into('<I', out, 12, len(out))
        return bytes(out)

