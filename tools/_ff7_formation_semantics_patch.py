from pathlib import Path

path = Path('games/ff7/semantics.py')
text = path.read_text(encoding='utf-8')


def replace(old, new):
    global text
    if old not in text:
        raise SystemExit('Expected semantics source block not found:\n' + old[:240])
    text = text.replace(old, new, 1)


anchor = 'CHOCOBO_RATINGS = ((1, "Wonderful"), (2, "Great"), (3, "Good"), (4, "Fair"), (5, "Average"), (6, "Poor"), (7, "Bad"), (8, "Terrible"))\n'
additions = '''CHOCOBO_RATINGS = ((1, "Wonderful"), (2, "Great"), (3, "Good"), (4, "Fair"), (5, "Average"), (6, "Poor"), (7, "Bad"), (8, "Terrible"))
BATTLE_LAYOUTS = (
    (0x00, "Normal"), (0x01, "Preemptive strike"), (0x02, "Back attack"),
    (0x03, "Side attack"), (0x04, "Pincer attack"), (0x05, "Pincer attack — variant 2"),
    (0x06, "Side attack — variant 2"), (0x07, "Side attack — variant 3"),
    (0x08, "Front row locked — Change disabled"),
)
# These logical flags are stored inverted in scene.bin. Scarlet performs the
# same inversion at its binary boundary; keeping it metadata-side lets the
# editor say what the battle *does* rather than what a zero bit happens to mean.
BATTLE_FLAGS = (
    (0x02, "Special multi-part battle behavior"),
    (0x04, "Cannot escape"),
    (0x08, "Skip victory fanfare / poses"),
    (0x10, "Disable preemptive-strike chance"),
)
INITIAL_CONDITIONS = (
    (0x01, "Visible at battle start"), (0x02, "Starts on the left side"),
    (0x04, "Unknown engine condition (0x04)"), (0x08, "Targetable at battle start"),
    (0x10, "Main AI script active"),
)
COVER_GROUPS = tuple((1 << index, f"Cover group {index + 1}") for index in range(5))
BATTLE_LOCATIONS = (
    (0x00, "Debug Room"), (0x01, "Bizarro Sephiroth — center"), (0x02, "Grassland"),
    (0x03, "Mt. Nibel"), (0x04, "Forest"), (0x05, "Beach"), (0x06, "Desert"),
    (0x07, "Snow"), (0x08, "Swamp"), (0x09, "Sector 1 Train Station"),
    (0x0A, "Reactor 1"), (0x0B, "Reactor 1 Core"), (0x0C, "Reactor 1 Entrance"),
    (0x0D, "Sector 4 Subway"), (0x0E, "Cave"), (0x0F, "Shinra HQ"),
    (0x10, "Midgar Raid Subway"), (0x11, "Hojo's Lab"), (0x12, "Shinra HQ Elevator"),
    (0x13, "Shinra HQ Roof"), (0x14, "Highway"), (0x15, "Wutai Pagoda"),
    (0x16, "Church"), (0x17, "Corel Valley"), (0x18, "Slums"), (0x19, "Corridors"),
    (0x1A, "Underground"), (0x1B, "Sector 7 Support Pillar Stairway"),
    (0x1C, "Sector 7 Support Pillar Top"), (0x1D, "Sector 8"), (0x1E, "Sewers"),
    (0x1F, "Mythril Mines"), (0x20, "Floating Platforms"), (0x21, "Corel Mountain Path"),
    (0x22, "Junon Beach"), (0x23, "Cargo Ship"), (0x24, "Corel Prison"),
    (0x25, "Battle Square"), (0x26, "Da Chao — Rapps battle"), (0x27, "Cid's Backyard"),
    (0x28, "Final Descent"), (0x29, "Reactor 5 Entrance"),
    (0x2A, "Temple of the Ancients — Escher Room"), (0x2B, "Shinra Mansion"),
    (0x2C, "Junon Airship Dock"), (0x2D, "Whirlwind Maze"),
    (0x2E, "Junon Underwater Reactor"), (0x2F, "Gongaga Reactor"), (0x30, "Gelnika"),
    (0x31, "Train Graveyard"), (0x32, "Ice Caves"), (0x33, "Sister Ray"),
    (0x34, "Sister Ray Base"), (0x35, "Forgotten City Altar"),
    (0x36, "Initial Descent"), (0x37, "Hatchery"), (0x38, "Water Area"),
    (0x39, "Safer Sephiroth battle"), (0x3A, "Kalm flashback — Dragon battle"),
    (0x3B, "Junon Underwater Pipe"), (0x3C, "Corel Reactor cliff — unused"),
    (0x3D, "Corel Railway Canyon"), (0x3E, "Whirlwind Maze Crater"),
    (0x3F, "Corel Railway Roller Coaster"), (0x40, "Wooden Bridge"), (0x41, "Da Chao"),
    (0x42, "Fort Condor"), (0x43, "Dirt Wasteland"), (0x44, "Bizarro Sephiroth — right"),
    (0x45, "Bizarro Sephiroth — left"), (0x46, "Jenova·SYNTHESIS battle"),
    (0x47, "Corel Train"), (0x48, "Cosmo Canyon"), (0x49, "Cave of the Gi"),
    (0x4A, "Shinra Mansion Basement"), (0x4B, "Temple of the Ancients — boss room"),
    (0x4C, "Temple of the Ancients — mural room"), (0x4D, "Temple of the Ancients — clock room"),
    (0x4E, "Final Battle"), (0x4F, "Jungle"), (0x50, "Highwind Deck"),
    (0x51, "Corel Reactor"), (0x52, "Unused"), (0x53, "Don Corneo's Mansion"),
    (0x54, "Underwater — Emerald Weapon"), (0x55, "Reactor 5"), (0x56, "Shinra HQ Escape"),
    (0x57, "Gongaga Reactor — Ultimate Weapon"), (0x58, "Corel Prison — Dyne battle"),
    (0x59, "Forest — Ultimate Weapon"),
)
'''
replace(anchor, additions)

old_setup = '''        "flags": advanced("Battle setup flags", "Packed battle-setup flags. Kept in Advanced until every bit has an authoritative name."),
        "layout": advanced("Battle layout code", "Formation layout code. Kept in Advanced instead of presenting an unexplained byte as a normal setting."),
        "location": advanced("Battle arena ID", "Battle arena/location ID. A human arena-name table is not yet available to this plugin."),
'''
new_setup = '''        "flags": _field(label="Battle restrictions", dataType="flags", flags=flags(*BATTLE_FLAGS), invertBits=True, bitWidth=16, group="Battle setup", help="Logical formation restrictions. scene.bin stores these four known flags inverted; Lexeditor shows their actual battle meaning. The special 0x02 behavior is used by multi-part formations but remains only partially understood."),
        "layout": _field(label="Battle layout", dataType="enum", choices=choices(*BATTLE_LAYOUTS), group="Battle setup", help="How the party and enemies are arranged when the fight begins: normal, preemptive, back/side/pincer variants, or front-row locked."),
        "location": _field(label="Battle arena", dataType="enum", choices=choices(*BATTLE_LOCATIONS), group="Battle setup", help="Battle background/arena used by this formation."),
        "cameraIndex": _field(label="Pre-battle camera", dataType="enum", choices=choices((0,"Camera 1"),(1,"Camera 2"),(2,"Camera 3")), group="Battle setup", help="Which of this formation's three stored camera placements is used before combat begins."),
'''
replace(old_setup, new_setup)

old_row = '''        **{f"slot{i}_row": _field(label=f"Enemy slot {i+1} row", dataType="enum", choices=choices((0,"Front row"),(1,"Back row")), group=f"Enemy slot {i+1}", help="Battle row for this enemy slot.") for i in range(6)},
'''
new_row = '''        **{f"slot{i}_row": _field(label=f"Enemy slot {i+1} depth row", group=f"Enemy slot {i+1}", help="Formation depth/order, not a simple front/back toggle. Lower-numbered rows stand in front of higher-numbered rows; shared cover groups can block short-range targeting of enemies farther back.") for i in range(6)},
'''
replace(old_row, new_row)

old_arena = '''for i in range(4):
    SCENE["encounters"][f"arena{i}"] = advanced(f"Arena candidate {i+1} ID", "Raw battle arena candidate ID; no authoritative arena-name table is available here.")
'''
new_arena = '''for i in range(4):
    SCENE["encounters"][f"arena{i}"] = reference("encounters", label=f"Battle Square next-battle candidate {i+1}", empty=65535, help="Formation that may follow this one during a Battle Square sequence; 65535 means no candidate.")
'''
replace(old_arena, new_arena)

old_slot = '''for slot in range(6):
    for suffix, label in (("cover","Cover flags"),("flags","Initial condition flags")):
        SCENE["encounters"][f"slot{slot}_{suffix}"] = advanced(f"Enemy slot {slot+1} {label}", "Packed formation-engine flags; retained under Advanced until every bit is authoritatively named.")
'''
new_slot = '''for slot in range(6):
    for axis, label in (("x","Position X"),("y","Position Y"),("z","Position Z")):
        SCENE["encounters"][f"slot{slot}_{axis}"] = _field(label=f"Enemy slot {slot+1} {label}", group=f"Enemy slot {slot+1}", help="Signed battle-space coordinate for this enemy's starting position.")
    SCENE["encounters"][f"slot{slot}_cover"] = _field(label=f"Enemy slot {slot+1} short-range cover groups", dataType="flags", flags=flags(*COVER_GROUPS), bitWidth=16, group=f"Enemy slot {slot+1}", help="Five group-membership bits used with formation depth. A front enemy blocks short-range targeting of a farther-back enemy when they share at least one cover group.")
    SCENE["encounters"][f"slot{slot}_flags"] = _field(label=f"Enemy slot {slot+1} starting conditions", dataType="flags", flags=flags(*INITIAL_CONDITIONS), bitWidth=32, group=f"Enemy slot {slot+1}", help="Known scene.bin starting-state bits: visibility, side, targetability and whether the main AI script starts active. The 0x04 bit is preserved and exposed honestly because its exact effect remains unknown.")
'''
replace(old_slot, new_slot)
path.write_text(text, encoding='utf-8')

test_path = Path('tools/verify_ff7_semantic_surface.py')
tests = test_path.read_text(encoding='utf-8')
needle = '        self.assertEqual(by["encounters"]["slot0_enemy"]["dataType"],"reference")\n'
insertion = needle + '''        self.assertEqual(by["encounters"]["layout"]["dataType"],"enum")
        self.assertEqual(by["encounters"]["location"]["dataType"],"enum")
        self.assertEqual(by["encounters"]["cameraIndex"]["dataType"],"enum")
        self.assertEqual(by["encounters"]["flags"]["dataType"],"flags")
        self.assertTrue(by["encounters"]["flags"]["invertBits"])
        self.assertEqual(by["encounters"]["arena0"]["dataType"],"reference")
        self.assertEqual(by["encounters"]["slot0_cover"]["dataType"],"flags")
        self.assertEqual(by["encounters"]["slot0_flags"]["dataType"],"flags")
        self.assertEqual(next(c for c in by["encounters"]["layout"]["choices"] if c["value"]==4)["label"],"Pincer attack")
        self.assertEqual(next(c for c in by["encounters"]["location"]["choices"] if c["value"]==0x25)["label"],"Battle Square")
        self.assertNotEqual(by["encounters"]["slot0_row"].get("dataType"),"enum")
'''
if needle not in tests:
    raise SystemExit('Expected semantic regression insertion point not found')
tests = tests.replace(needle, insertion, 1)
test_path.write_text(tests, encoding='utf-8')
