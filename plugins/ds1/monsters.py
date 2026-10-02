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


# All help lives with the property definition. Guard status fields and other
# effects remain untouched: their annotation does not distinguish damage from
# buildup clearly enough to expose them as percentage resistance controls.
RESISTANCES = {}
for key, kind in [('def_phys', 'Physical'), ('def_mag', 'Magic'),
                  ('def_fire', 'Fire'), ('def_thunder', 'Lightning')]:
    RESISTANCES[key] = (kind, 'Damage defense',
        f'Defense rating against {kind.lower()} damage. This is not a fixed amount subtracted from each hit.')
for key, kind in [('def_slash', 'Slash'), ('def_blow', 'Strike'), ('def_thrust', 'Thrust')]:
    RESISTANCES[key] = (kind + ' (%)', 'Physical defense modifiers',
        f'Adjusts physical defense against {kind.lower()} attacks by this percentage. '
        '25 means 25% more defense, not 25% less damage.')
for key, kind in [('resist_poison', 'Poison'), ('resist_desease', 'Toxic'),
                  ('resist_blood', 'Bleed'), ('resist_curse', 'Curse')]:
    RESISTANCES[key] = (kind, 'Status buildup resistance',
        f'Resistance to {kind.lower()} buildup. This is separate from damage defense and is not a percentage.')
for key, kind in [('physGuardCutRate', 'Physical'), ('magGuardCutRate', 'Magic'),
                  ('fireGuardCutRate', 'Fire'), ('thunGuardCutRate', 'Lightning'),
                  ('slashGuardCutRate', 'Slash'), ('blowGuardCutRate', 'Strike'),
                  ('thrustGuardCutRate', 'Thrust')]:
    RESISTANCES[key] = (kind + ' (%)', 'Guard absorption',
        f'Reduces {kind.lower()} damage while this monster guards. This does not apply to an unguarded hit.')
