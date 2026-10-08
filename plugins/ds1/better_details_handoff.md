# dark souls remastered: better details handoff

## current branch

- branch: `codex/ds1-better-details`
- pr: #917
- base: `master`
- current committed head: `48c73935ff0f3528661b9936e00307cc0d9d5e32`

## important correction from ui review

the weapon details screen has **two separate empty stat lines** available for the new information.

use:

1. **one line in the left column, immediately above `parambonus`**
   - label/value: poise damage
   - this is its own row, not a replacement for any existing atk row

2. **one line in the right column, immediately above `reqparam`**
   - label/value: stamina cost
   - this is its own row, not a replacement for stability or any other existing stat

do **not** treat these as one shared y-position. the screenshot confirms they are two independent row slots in the existing menu layout.

## intended presentation

for the ordinary melee weapon detail page:

- keep all vanilla atk rows
- keep all vanilla dmg reduction rows
- keep parambonus
- keep reqparam
- keep durability
- keep weight
- insert:
  - `poise` row above parambonus
  - `stamina` row above reqparam

recommended labels:

- `poise`
- `stamina cost`

show the number in the same right-aligned style used by nearby numeric fields.

fractional poise values may be displayed to one decimal place. stamina cost is normally an integer.

invalid/unresolved values should display `--`, never a fabricated zero.

## data model already implemented

`plugins/ds1/weapon_details.py` contains the read-only data resolver and tests.

it deliberately distinguishes:

- weapon `saWeaponDamage`: base poise attack value
- reinforcement `saWeaponAtkRate`: reinforcement scaling
- selected player attack `atkSuperArmorCorrection`: attack-specific poise correction
- `AtkParam_Pc.atkSuperArmor`: fixed poise path
- `BehaviorParam_PC.stamina`: action stamina cost
- `EquipParamWeapon.attackBaseStamina`: defender stamina damage, **not** the attack's stamina cost

the resolver handles upgraded weapon ids and reinforcement lookup. it refuses to invent values for missing or non-direct references.

## action/reference handling

the ui should expose a concrete reference choice for the displayed move instead of pretending every weapon has one universal stamina cost.

the current resolver supports explicit behavior ids and variation validation. it does not infer that a random behavior id is automatically “r1” without an explicit selection.

recommended first implementation:

- setting: `reference = 1h_opening_light`
- setting: `reference = 2h_opening_light`

the currently selected reference does not automatically follow live stance unless native runtime state is later wired in.

## native implementation direction

the old encumbrance percentage implementation already demonstrates the required native pattern:

- patch the existing menu text path
- preserve the original formatter/call
- use existing text/node setters
- avoid adding a renderer or dll
- compose through the existing ds1 executable tweak system

the first candidate native design used the unused sixth melee stat slot as a target, but that is **not** the desired final layout.

the final implementation should target the two existing blank rows described above.

## acceptance requirements

verify in the actual game, not just synthetic fixtures:

- stone greatsword and several other melee weapons
- 1h and 2h references
- upgraded weapons
- weapon switching without reopening the menu
- zero and fractional poise
- missing/unresolved data
- empty hand / non-melee items
- bows and catalysts
- comparison screens
- small and large ui scale
- clipping and alignment
- menu reopen / close
- disable -> exact vanilla behavior

the screenshot supplied during handoff is the authoritative ui/layout correction for this task.
