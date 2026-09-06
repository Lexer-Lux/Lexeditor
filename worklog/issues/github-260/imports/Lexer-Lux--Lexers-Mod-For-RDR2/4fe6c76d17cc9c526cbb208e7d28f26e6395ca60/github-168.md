# GitHub #168 - Belt lantern size

## Recurrence audit before source edits

- Primary evidence is Rockstar's native database. It resolves
  `_SET_WEAPON_SCALE(Object,float)` and `_GET_WEAPON_SCALE(Object)`. Story shop
  scripts use the setter on weapon objects. No entity-transform guess is used.
- The belt lantern is the module's created weapon-model object. Scale is applied
  once after creation and only when the hot-reloaded value changes. It is not a
  per-frame transform fight.
- The getter and log record the applied value. A setter call alone is not
  accepted as proof.
- Player-visible acceptance still requires changing Scale above and below 1.0
  and seeing the attached lantern change size without detaching, clipping more,
  respawning each frame, or changing light range.

## Implementation

Added `[BeltLantern] Scale`, default 1.0 and bounded 0.25-2.0. The normal INI
watcher hot-reloads it. The module applies Rockstar's weapon-object scale native
after spawn and on a changed value, then reads the scale back. Light Range and
Brightness remain independent.

## Returned-test audit before repair

- The installed log repeatedly recorded `requested=0.25 applied=1.0`. The setter executed, but its getter disproved the result. Repeating the setter every health poll was also an engine fight.
- Exact cause: the module created a generic object with `CREATE_OBJECT_NO_OFFSET`, then called a native whose documented parameter is `weaponObject`. The matching Rockstar constructor `_CREATE_WEAPON_OBJECT` has an explicit scale argument and returns the required weapon-object type.
- Repair path: create the lantern as its real `WEAPON_MELEE_*` weapon object with the requested scale. Retain the getter as an immediate postcondition. A failed readback must latch and must not retry every poll.
- Player-visible acceptance remains a size change at 0.25 and 2.0 while the same attachment, radial toggle, and light range continue to work.
