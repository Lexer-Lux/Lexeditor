"""Reviewed DS1R monster families and the resistance-only editing boundary.

Evidence: pinned Smithbox DS1R NpcParam row names, NPC_TYPE and PARAMDEF in
metadata/SOURCE.json. Names alone are insufficient: the live npcType must also
be Standard Enemy (0). Stray Demon is 0 too, so a type-only filter is unsafe.
Mixed boss families (Capra/Taurus, Pinwheel, Butterfly, Sanctuary Guardian),
boss body parts, named NPCs, test rows, and unknown/custom IDs are not admitted.
Egg Carrier's named NPC variant (321001) is type 2 and therefore excluded.
These are parameter variants, not proof of individual map placements.
"""

MONSTER_FAMILIES = frozenset({
    'Rat', 'Small Rat', 'Giant Rat', 'Plague Rat', 'Infested Ghoul',
    'Batwing Demon', 'Mushroom Parent', 'Mushroom Child', 'Prowling Demon',
    'Crow Demon', 'Demonic Foliage', 'Channeler', 'Stone Knight', 'Darkwraith',
    'Painting Guardian', 'Silver Knight', 'Demonic Statue', 'Hollow',
    'Undead Assassin', 'Blowdart Hollow', 'Hollow Warrior', 'Hollow Soldier',
    'Balder Knight', 'Heavy Knight', 'Necromancer', 'Butcher', 'Ghost (Male)',
    'Ghost (Female)', 'Serpent Soldier', 'Serpent Mage', 'Crystal Golem',
    'Crystal Golem (Gold)', 'Mimic', 'Black Knight', 'Black Knight (Ghost)',
    'Crystal Hollow', 'Infested Barbarian (Club)', 'Infested Barbarian (Boulder)',
    'Hollow Phalanx', 'Engorged Hollow', 'Giant', 'Royal Sentinel', 'Skeleton',
    'Giant Skeleton', 'Bonewheel Skeleton', 'Skeleton Baby', 'Skeleton Beast',
    'Bone Tower', 'Mosquito', 'Slime', 'Egg Carrier', 'Chaos Bug', 'Chaos Eater',
    'Maneater Clam', 'Basilisk', 'Crystal Lizard', 'Pisaca', 'Undead Attack Dog',
    'Flaming Attack Dog', 'Walking Tree', 'Tree Lizard', 'Leech', 'Burrower',
    'Cragspider', 'Frog-Ray', 'Armored Tusk', 'Armored Tusk - Reinforced',
    'Vagrant (Passive)', 'Vagrant (Aggressive) - 1', 'Vagrant (Aggressive) - 2',
    'Mass Of Souls', 'Wisp', 'Drake', 'Stone Guardian', 'Scarecrow', 'Bloathead',
    'Bloathead Sorcerer', 'Humanity Phantom (Large)', 'Humanity Phantom (Medium)',
    'Humanity Phantom (Small)', 'Chained Prisoner', 'Undead Attack Dog (DLC)',
    'Parasitic Wall Hugger', 'Great Feline',
})


def classified_monster(row_id, reference_name, npc_type):
    return row_id >= 120000 and reference_name in MONSTER_FAMILIES and npc_type == 0


def duplicate_stem(name, row_id):
    """The family stem of a Lexeditor-duplicated row name ("Rat (1000000)"),
    or None. No family name ends in digits in parentheses, so the suffix
    only matches names this editor wrote when duplicating."""
    suffix = f' ({row_id})'
    if name and name.endswith(suffix) and len(name) > len(suffix):
        return name[:-len(suffix)]
    return None


def base_stem(name):
    """A row name without any Lexeditor duplicate suffixes."""
    stem = name or ''
    while True:
        head, space, tail = stem.rpartition(' (')
        if not space or not tail.endswith(')') or not tail[:-1].isdigit():
            return stem
        stem = head


# All help lives with the property definition. Guard status fields and other
# effects remain untouched: their annotation does not distinguish damage from
# buildup clearly enough to expose them as percentage resistance controls.
RESISTANCES = {}
for key, kind in [('def_phys', 'Physical'), ('def_mag', 'Magic'),
                  ('def_fire', 'Fire'), ('def_thunder', 'Lightning')]:
    RESISTANCES[key] = (f'{kind} defense', 'Defense',
        f'Flat defense against {kind.lower()} damage, in the same units as the player\'s defense: '
        'a whole number of 0 or more, not a percentage. The game weighs it against the attack\'s '
        'damage, so the same defense blocks more of a weak hit than of a strong one. Armor Rework '
        'sets it to 0 and gives the enemy percentage absorption instead.')
for key, kind in [('def_slash', 'Slash'), ('def_blow', 'Strike'), ('def_thrust', 'Thrust')]:
    RESISTANCES[key] = (f'{kind} vs physical (%)', 'Defense',
        f'Changes physical defense against {kind.lower()} attacks by this percentage: -100 makes it 0, '
        '25 makes it 25% higher. It does not reduce damage by 25%.')
for key, kind in [('resist_poison', 'Poison'), ('resist_desease', 'Toxic'),
                  ('resist_blood', 'Bleed'), ('resist_curse', 'Curse')]:
    RESISTANCES[key] = (f'{kind} resistance', 'Defense',
        f'How much {kind.lower()} buildup this enemy takes before it is afflicted: each hit adds its '
        f'weapon\'s {kind.lower()} value, and the enemy is afflicted at this total. Not a percentage. '
        + ('Every vanilla enemy has 0, because nothing the player has inflicts curse.'
           if kind == 'Curse' else ''))
# Weapons and spells of these kinds deal extra damage to an enemy that has
# the flag (Divine weapons, Occult weapons; Abyssal is the Abyss Walking flag).
WEAKNESSES = {'isWeakSaint': ('Weak to Divine', 'Divine weapons deal extra damage to this enemy.'),
              'isWeakA': ('Weak to Occult', 'Occult weapons deal extra damage to this enemy.'),
              'isWeakB': ('Abyssal', 'Marks the enemy as of the Abyss.')}
for key, (label, description) in WEAKNESSES.items():
    RESISTANCES[key] = (label, 'Defense', description)
for key, kind in [('physGuardCutRate', 'Physical'), ('magGuardCutRate', 'Magic'),
                  ('fireGuardCutRate', 'Fire'), ('thunGuardCutRate', 'Lightning'),
                  ('slashGuardCutRate', 'Slash'), ('blowGuardCutRate', 'Strike'),
                  ('thrustGuardCutRate', 'Thrust')]:
    RESISTANCES[key] = (kind + ' (%)', 'Blocking', '')

# Reviewed combat stats, drops, passive effects and AI links. Damage
# multipliers state their unchanged baseline of 1, the way effect
# multipliers do.
NPC_STATS = {
    'hp': ('HP', 'Basics', 'Maximum health before resident effects scale it; Effective HP shows the result. The enemy dies at 0.'),
    'mp': ('MP', 'Basics', 'Maximum mana.'),
    'stamina': ('Stamina', 'Basics', 'Maximum stamina. Enemies use it when they block.'),
    'staminaRecoverBaseVel': ('Stamina recovery (stamina/second)', 'Basics',
        'Stamina points recovered per second. Higher values recover faster.'),
    'superArmorDurability': ('Poise', 'Basics',
        "Poise health. Only works when the enemy's damage level is set."),
    'superArmorRecoverCorrection': ('Poise recovery', 'Basics',
        'Adjusts poise recovery speed. 0 is unchanged.'),
    'superArmorBrakeKnockbackDist': ('Poise-break stagger', 'Basics',
        'How hard the enemy staggers when its poise breaks. Higher values throw it further.'),
    'disableRespawn': ('No bonfire reset', 'Basics',
        'When set, this enemy keeps its position and behavior when the player rests at a bonfire.'),
    'teamType': ('Team', 'Basics', 'Which side this enemy fights for.'),
    'weakPartsDamageRate': ('Damage taken: weak point (x)', 'Defense',
        'Multiplier on damage the weak point takes. 1 is unchanged.'),
    'staminaGuardDef': ('Stamina guard (%)', 'Blocking', ''),
    'hitHeight': ('Body height', 'Defense',
        'Height of the body used for hits. Ignored for ragdoll bodies.'),
    'hitRadius': ('Body radius', 'Defense',
        'Radius of the body used for hits. Ignored for ragdoll bodies.'),
    'hitYOffset': ('Body offset', 'Defense',
        'Vertical shift of the body used for hits. Positive values float the enemy.'),
    'getSoul': ('Souls', 'Value & rewards', 'Souls dropped on death.'),
    'humanityLotId': ('Humanity drop table', 'Value & rewards',
        'Humanity lot dropped on death, as a lot ID from the Drops list. -1 drops nothing.'),
    'dropType': ('Drop style', 'Value & rewards',
        'How dropped items appear: on the corpse or on the ground.'),
    'GameClearSpEffectID': ('Cleared-game effect', 'Effects & references',
        'An effect active only on NG+ and higher. Used to scale enemies per journey.'),
    'aiThinkId': ('AI table', 'Effects & references',
        'The AI table this enemy thinks with, picked from the AI list.'),
}
for index in range(1, 9):
    NPC_STATS[f'partsDamageRate{index}'] = (
        f'Damage taken: Part {index} (x)', 'Defense',
        f'Multiplier on damage body part {index} takes. 1 is unchanged.')
for key, kind in [('poisonGuardResist', 'Poison'), ('diseaseGuardResist', 'Toxic'),
                  ('bloodGuardResist', 'Bleed'), ('curseGuardResist', 'Curse')]:
    NPC_STATS[key] = (f'{kind} guard (%)', 'Blocking', '')
for index in range(1, 7):
    NPC_STATS[f'itemLotId_{index}'] = (
        f'Drop table {index}', 'Value & rewards',
        'Item lot dropped on death, as a lot ID from the Drops list. -1 drops nothing.')
for index in range(8):
    NPC_STATS[f'spEffectID{index}'] = (
        f'Passive effect {index + 1}', 'Effects & references',
        'An effect always active on this enemy.')
NPC_FIELDS = {**RESISTANCES, **NPC_STATS}
