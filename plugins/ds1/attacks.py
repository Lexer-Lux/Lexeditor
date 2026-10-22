"""Enemy damage fields and explicit parameter-reference tracing.

Smithbox's pinned MIT metadata defines NpcParam.behaviorVariationId and
BehaviorParam.variationId as the same virtual reference, refType 0/1 as
attack/projectile, and Bullet.atkId_Bullet / HitBulletID as attack/child links.
Matching variation fields proves a parameter association, not an animation
invocation. No row-number or translated-name ownership heuristic is used.
"""
from collections import defaultdict

ATTACK_FIELDS = {
    key: (label, 'Base damage', f'Base {label.lower()} attack power before defense and other modifiers. This is not the final health lost.')
    for key, label in [('atkPhys', 'Physical'), ('atkMag', 'Magic'),
                       ('atkFire', 'Fire'), ('atkThun', 'Lightning')]
}
ATTACK_FIELDS['atkAttribute'] = ('Physical type', 'Base damage',
    'Selects the physical defense used against this attack. Standard has no slash, strike or thrust attribute.')

# Each attack carries four hit slots. A slot's size and its two model points
# place the hitbox on the attacker; Smithbox's MIT annotations define the
# radius and dummy-point placement. Priority breaks ties when slots strike
# together. Hit type stays protected: its collision-type values are not
# documented well enough to expose.
for _slot in range(4):
    ATTACK_FIELDS[f'hit{_slot}_Radius'] = (
        f'Hit {_slot}: Size (metres)', 'Hitbox',
        f"How large hit slot {_slot}'s hitbox is. Larger values hit a wider area.")
    ATTACK_FIELDS[f'hit{_slot}_DmyPoly1'] = (
        f'Hit {_slot}: First point', 'Hitbox',
        f"The model point hit slot {_slot} follows. Use an ID from the attacker's model.")
    ATTACK_FIELDS[f'hit{_slot}_DmyPoly2'] = (
        f'Hit {_slot}: Second point', 'Hitbox',
        f"The second model point for hit slot {_slot}. It shapes the hitbox together with the first point.")
    ATTACK_FIELDS[f'hti{_slot}_Priority'] = (
        f'Hit {_slot}: Priority', 'Hitbox',
        'Which hit wins when several slots strike at once. Higher values win.')
ATTACK_FIELDS['hitSourceType'] = (
    'Hitbox source', 'Hitbox',
    'Which part of the attacker the hitbox points attach to.')
ATTACK_FIELDS['knockbackDist'] = (
    'Knockback', 'Impact',
    'How hard this attack knocks the victim back. Higher values throw the victim further.')
ATTACK_FIELDS['hitStopTime'] = (
    'Hit pause (seconds)', 'Impact',
    "How long the victim's animation pauses when hit, in seconds.")

# Every editable Bullet property in presentation order: lifetime, how
# it flies, how it homes, how it spreads, what it hits, what it
# dampens, its flags, then its links. Annotations keep the labels;
# this map only sorts the detail panel into sections.
BULLET_GROUPS = {
    'life': 'Lifetime & range', 'dist': 'Lifetime & range',
    'dmgHitRecordLifeTime': 'Lifetime & range',
    'initVellocity': 'Flight', 'accelInRange': 'Flight',
    'accelOutRange': 'Flight', 'maxVellocity': 'Flight',
    'minVellocity': 'Flight', 'accelTime': 'Flight',
    'gravityInRange': 'Flight', 'gravityOutRange': 'Flight',
    'homingBeginDist': 'Homing', 'homingAngle': 'Homing',
    'hormingStopRange': 'Homing', 'hormingOffsetRange': 'Homing',
    'autoSearchNPCThinkID': 'Homing',
    'numShoot': 'Spread', 'shootInterval': 'Spread',
    'shootAngle': 'Spread', 'shootAngleInterval': 'Spread',
    'shootAngleXInterval': 'Spread', 'shootAngleXZ': 'Spread',
    'spreadTime': 'Spread', 'expDelay': 'Spread',
    'lockShootLimitAng': 'Spread',
    'hitRadius': 'Hitbox', 'hitRadiusMax': 'Hitbox',
    'isPenetrate': 'Hitbox', 'isPenetrateMap': 'Hitbox',
    'isHitBothTeam': 'Hitbox', 'isEndlessHit': 'Hitbox',
    'damageDamp': 'Damage', 'spelDamageDamp': 'Damage',
    'fireDamageDamp': 'Damage', 'thunderDamageDamp': 'Damage',
    'staminaDamp': 'Damage', 'knockbackDamp': 'Damage',
    'isAttackSFX': 'Flags', 'isHitForceMagic': 'Flags',
    'isHitDarkForceMagic': 'Flags',
    'atkId_Bullet': 'Attack & effects',
    'HitBulletID': 'Attack & effects',
    'spEffectId0': 'Attack & effects',
    'spEffectId1': 'Attack & effects',
    'spEffectId2': 'Attack & effects',
    'spEffectId3': 'Attack & effects',
    'spEffectId4': 'Attack & effects',
    'spEffectIDForShooter': 'Attack & effects',
    'atkAttribute': 'Attack & effects',
    'spAttribute': 'Attack & effects',
    'launchConditionType': 'Attack & effects',
    'FollowType': 'Attack & effects',
}


def hitbox_slots(document, attack_id):
    """One attack's four hit slots: radius, model points, and whether
    the slot strikes. A slot with no radius or no first point is idle;
    a second point stretches the sphere into a capsule."""
    slots = []
    for slot in range(4):
        radius = document.value('AtkParam_Npc', attack_id, f'hit{slot}_Radius')
        first = document.value('AtkParam_Npc', attack_id, f'hit{slot}_DmyPoly1')
        second = document.value('AtkParam_Npc', attack_id, f'hit{slot}_DmyPoly2')
        active = radius > 0 and first >= 0
        slots.append({'slot': slot, 'radius': radius, 'first': first, 'second': second,
                      'active': active, 'shape': 'capsule' if active and second >= 0 else 'sphere'})
    return slots


def body_hitbox(document, npc_id):
    """The body's own hitbox: radius, height and vertical shift."""
    return {'radius': document.value('NpcParam', npc_id, 'hitRadius'),
            'height': document.value('NpcParam', npc_id, 'hitHeight'),
            'offset': document.value('NpcParam', npc_id, 'hitYOffset')}


class AttackReferences:
    def __init__(self, document):
        self.doc = document
        self.attack_ids = {r.row_id for r in document.params['AtkParam_Npc'].rows}
        self.choices = {'-1': 'None'}
        for row in document.params['AtkParam_Npc'].rows:
            self.choices[str(row.row_id)] = document.display_name('AtkParam_Npc', row.row_id, row)
        self.bullets = {r.row_id: (document.value('Bullet', r.row_id, 'atkId_Bullet'),
                                  document.value('Bullet', r.row_id, 'HitBulletID'))
                        for r in document.params['Bullet'].rows}
        self.variants = defaultdict(list)
        for row in document.params['NpcParam'].rows:
            self.variants[document.value('NpcParam', row.row_id, 'behaviorVariationId')].append(row.row_id)
        self.by_variation = defaultdict(list)
        self.paths = defaultdict(list)
        self.issues = defaultdict(list)
        for row in document.params['BehaviorParam'].rows:
            variation = document.value('BehaviorParam', row.row_id, 'variationId')
            kind = document.value('BehaviorParam', row.row_id, 'refType')
            target = document.value('BehaviorParam', row.row_id, 'refId')
            self.by_variation[variation].append(row.row_id)
            prefix = f'Behavior {row.row_id}'
            if kind == 0:
                self._attack(variation, row.row_id, target, prefix, False)
            elif kind == 1:
                visited = set()
                while target >= 0:
                    prefix += f' → Bullet {target}'
                    if target in visited:
                        self.issues[variation].append(prefix + ' (cycle)'); break
                    if target not in self.bullets:
                        self.issues[variation].append(prefix + ' (missing)'); break
                    visited.add(target)
                    attack, child = self.bullets[target]
                    if attack >= 0: self._attack(variation, row.row_id, attack, prefix, True)
                    target = child
            elif kind == 2:
                self.issues[variation].append(prefix + f' → effect {target} (damage not traced)')
            else:
                self.issues[variation].append(prefix + f' (unsupported reference type {kind})')

    def _attack(self, variation, behavior, attack, path, projectile):
        path += f' → Attack {attack}'
        if attack not in self.attack_ids:
            self.issues[variation].append(path + ' (missing)')
        else:
            self.paths[attack].append({'variation': variation, 'behavior': behavior,
                                       'path': path, 'projectile': projectile})

    def list(self, monster_id, all_records=False):
        if not (self.doc.is_monster(monster_id) or self.doc.is_friend(monster_id)
                or self.doc.is_merchant(monster_id) or self.doc.is_boss(monster_id)):
            raise ValueError('Select a reviewed monster or NPC')
        variation = self.doc.value('NpcParam', monster_id, 'behaviorVariationId')
        rows = []
        for attack in sorted(self.attack_ids):
            paths = [p for p in self.paths[attack] if p['variation'] == variation]
            if not all_records and not paths: continue
            routes = {p['projectile'] for p in paths}
            route = ('Direct + projectile' if len(routes) == 2 else 'Projectile' if True in routes
                     else 'Direct' if routes else 'Not linked')
            rows.append({'id': attack, 'table': 'AtkParam_Npc', 'name': self.doc.schemas['AtkParam_Npc']['names'].get(attack)
                         or f'Attack {attack}', 'route': route})
        return {'rows': rows, 'variation': variation, 'behaviorCount': len(self.by_variation[variation]),
                'unresolved': self.issues[variation]}

    def moves(self, variation):
        """One behavior set's moves: each row with the attack, projectile
        or effect it calls."""
        rows = []
        for behavior in sorted(self.by_variation[variation]):
            kind = self.doc.value('BehaviorParam', behavior, 'refType')
            target = self.doc.value('BehaviorParam', behavior, 'refId')
            rows.append({'id': behavior, 'table': 'BehaviorParam',
                         'name': self.doc.display_name('BehaviorParam', behavior),
                         'target': self._move_target(kind, target)})
        return rows

    def _move_target(self, kind, target):
        if kind == 0:
            if target in self.attack_ids:
                return {'kind': 'attack', 'table': 'AtkParam_Npc', 'id': target,
                        'name': self.doc.display_name('AtkParam_Npc', target),
                        'projectile': False}
            return {'kind': 'missing', 'detail': f'Attack {target} is not in the parameters'}
        if kind == 1:
            path, visited = f'Bullet {target}', set()
            while target >= 0:
                if target in visited:
                    return {'kind': 'missing', 'detail': path + ' (cycle)'}
                if target not in self.bullets:
                    return {'kind': 'missing', 'detail': path + ' (missing)'}
                visited.add(target)
                attack, target = self.bullets[target]
                if attack >= 0:
                    if attack in self.attack_ids:
                        return {'kind': 'attack', 'table': 'AtkParam_Npc', 'id': attack,
                                'name': self.doc.display_name('AtkParam_Npc', attack),
                                'projectile': True, 'path': path}
                    return {'kind': 'missing', 'detail': path + f' -> Attack {attack} (missing)'}
                path += f' -> Bullet {target}'
            return {'kind': 'missing', 'detail': path + ' (no attack)'}
        if kind == 2:
            params = self.doc.params.get('SpEffectParam')
            effect_ids = {row.row_id for row in params.rows} if params is not None else set()
            if target in effect_ids:
                return {'kind': 'effect', 'table': 'SpEffectParam', 'id': target,
                        'name': self.doc.display_name('SpEffectParam', target),
                        'projectile': False}
            return {'kind': 'missing', 'detail': f'Effect {target} is not in the parameters'}
        return {'kind': 'unsupported', 'detail': f'Unsupported reference type {kind}'}

    def impact(self, attack):
        paths = self.paths[attack]
        owners = sorted({npc for p in paths for npc in self.variants[p['variation']]})
        return {'variants': [{'id': npc, 'name': self.doc.schemas['NpcParam']['names'].get(npc) or f'NPC {npc}'}
                             for npc in owners],
                'behaviors': sorted({p['behavior'] for p in paths}),
                'bulletReferences': sorted(b for b, (a, _) in self.bullets.items() if a == attack),
                'paths': [p['path'] for p in paths]}
