# Lexeditor UI manual

This manual defines the shared UI language. A game plugin supplies data and a
theme. It must not rebuild these controls for each page.

## Panels and composition

A **panel** is one bounded content surface. A page composes one or more panels.
Every pair of adjacent panels gets the shared resize handle automatically.
Right-click resets a handle to that page's default.

Panel spacing is one responsive percentage. The same value applies between a
panel and the window edge, between adjacent panels, and between the tab bar and
page content. This keeps the visual rhythm stable on different screen sizes.

The shared composer sizes the content, not an empty footer. A full fixed list
divides its available height between its configured rows. A short list can end
after its last row. Filtering does not change the configured row height.

Blank Game is the unthemed framework gallery. Its one-, two-, and three-panel
tabs show the shared composer without a game theme. Its Subtabs page shows the
shared nested-navigation control. Use these pages to diagnose shared defaults
before adding or changing a game-specific override.

## Subtabs

A **subtab bar** navigates related views inside one top-level tab. It uses the
shared `subtabBar()` control, keyboard focus, selected state, and theme tokens.
A plugin supplies only the labels, current subtab, and change callback. It must
not copy a top-level tab bar or create unrelated private button styling.

## Table panels

A **Table panel** is a record list with columns. It supplies:

- sorting from every sortable header;
- drag-and-drop column order;
- columns controlled by pins in the related Detail panel;
- fixed row geometry during search;
- pagination without a vertical scrollbar;
- wheel navigation between pages;
- a per-page row override in Developer Mode.

The selected FF8 record uses an overlaid hand. The hand does not take layout
space or move header text.

Numeric columns use **magnitude alignment**. Values align on the decimal
boundary. Larger integer magnitudes extend to the left. Fractional precision
extends to the right. For example, `100`, `10`, and `0.9999` keep the same
decimal boundary instead of using simple right alignment.

## Detail panels

A **Detail panel** edits one selected record. It has one identity heading and
groups of rows. Every row uses the same label-to-value division. A plugin can
change that division for a page, but individual rows do not choose unrelated
positions.

A **property** is one labeled row in a Detail panel. A property holds one
**variable** in the ordinary case and several tightly related variables in a
**multi-variable property** - a stat block, a junction set, a pair of linked
readings. Related booleans that together describe one concept belong in one
multi-boolean property row (the shared `toggleRow()` control); they are not
split into a stack of separate properties just because the source format stores
them as separate bits or columns.

Copying follows the variable, not the row. A single-variable property has one
copy button and copies its value. A multi-variable property gives **each
variable its own copy button**; it never offers one button that silently hands
back the first variable it finds. A property whose switches are one stored
word - a bitflag row - copies the bare word, because the word is what the
property really is; the switches drawn over it are how it is read, not what it
holds.

A group title is an in-flow divider in the neutral shared theme. A game theme
can deliberately overlap it with the group border, as FF8 does, without
changing the shared structure. Fields can contain text, numbers, booleans,
flags, references, Thing Selectors, or compact custom controls.

A record's **name is its heading**, and the heading is where it is edited. A
detail panel that can rename its record types into the heading in place, and
the record's name column in the master table is editable too. A name is never
also an ordinary property row: that showed the name twice and made the copy
being read the copy that could not be changed.

Each pinnable field has a pin at the top-right of its control. A filled pin
means that the field is visible as a Table column. Clicking it removes the
column. Hovering an unpinned field shows the available pin. Column changes
re-fit the Table and panel divider.

## Vanilla and reference values

A **ref rail** is one source's reading of a property: a short tag and that
source's value. A **ref pillar** is the stack of rails beside a property. The
pillar shows only the sources that differ from the current value, so a rail
appears when an edit moves away from its source and disappears when the edit
lands back on it. `V` means Vanilla; other short tags name reference mods.
Clicking a rail restores that source's value. Booleans display a check or an
X, not their raw stored number or the words `true` and `false`.

A pillar holds at most four rails. Vanilla is always first and green. At most
three reference mods can follow it: the first is red, the second is blue, and
the third is yellow. A plugin must reject a fourth active reference mod
instead of clipping, wrapping, or hiding it.

**A pillar never moves anything.** Its width is reserved before any value is
known, from the longest tag and the longest value the panel's sources can ever
produce, and every value box on that panel ends at that one edge. Nothing the
reader types may change it: a rail appearing, a rail disappearing, or a value
growing by three digits all leave every box exactly where it was. A value too
long for the reserved width is shortened rather than allowed to widen it -
thousands to `12K`, millions to `3.4M`, billions to `1.2B`, a long word to its
first characters and an ellipsis. The rail's tooltip carries the exact value,
and clicking it still writes the exact value.

**A pillar never changes its property's height.** It is capped at the row it
annotates, and its rails share that height between them, so a three-deep
pillar is a smaller pillar rather than a taller row.

Within a pillar the tag and the value are two columns. Every tag starts on one
edge and every value on another, so a pillar mixing `V` with `R1` does not
step its numbers sideways by the width of the tag in front of them.

An **internal-ref box** puts the pillar inside the field's right edge. The
field is wider and reserves that internal space from the start. A unit suffix
moves left when the pillar is visible, so the reference remains to the right of
the unit. Multiple rails become smaller and stack within the same reserved
area. FF8 Hit Rate uses two linked internal-ref boxes: percent and raw value
out of 255.

Rail values always use the same player-facing format as the live value, subject
to the shortening above. An enum shows its name. An item shows its icon and
name. A boolean shows a check or X. A transformed number shows its transformed
unit.

## Units and booleans

A unit is part of its field, and it belongs to the **number**, not to the box.
It can be a suffix such as `%`, `/255`, `G`, or `×`, or a prefix when the game
requires one. A suffix sits immediately after the last digit of the value and
travels with it as the value is typed, measured in the box's own font. Pinning
it to the far edge of the box marked where the box ended rather than where the
value did, which on a wide panel put a `G` most of a screen away from the price
it qualifies.

This holds inside an **internal-ref box** too. The unit stops short of whatever
that box reserves on its right, so the unit and the reference never collide
however long the number grows; when the value is long enough to reach the
reserved lane the unit parks against it. So `50,000 G` reads as one thing, and
its `V 30,000` keeps its own lane to the right of it.

Unit placement is shared so game fonts cannot create local alignment errors.

Every variable uses the most human-friendly semantic control available; its raw
storage representation is an implementation detail, not UI. Booleans are normally
checkboxes. A **checkless toggle** is the compact on/off alternative when a checkbox
would add visual noise. A stored `0/1` is never exposed as a numeric field. Enums
show named choices. Bitflags are decomposed into a property group of checkboxes,
checkless toggles and/or enum controls as appropriate; never expose a whole flag
byte or integer merely because that is how the game stores it. Raw numbers are for
values that are genuinely numeric to a human.

## Thing Selectors and Searchers

A **Thing Selector** replaces a small drop-down when a field refers to another
record. It shows the current record's player-facing display and a magnifying
glass immediately after the text. It uses all available cell width without a
nested decorative box.

Activating it starts a **Searcher**. Lexeditor opens the target Table, blocks
ordinary navigation, and explains what to select. Holding a result fills its
row background without covering its content. Completion returns to the source
field. Cancel returns without a change. The context control can move between
the source and target while Searcher mode stays active.

## Hoverables and help

The small circle carrying a question mark beside a property is a **help pip**.
It is the one name for it: in the code it is `infoHelp()` and the
`lex-info-help` class, and everywhere else it is a help pip. A pip carries
authored semantic help and nothing else - never a restatement of the label, the
storage type, the bounds, the step, the unit, or the edit operation, all of
which the property already says elsewhere.

A pip lives on a rail and replaces that rail's type code while the rail is
pointed at. Its glyph is shared chrome: it keeps one size relative to its own
circle in every plugin theme, so a game font cannot crowd the question mark
against the ring around it.

A **hoverable** looks and behaves like a link to another editable record. The
same linked record has the same hover behavior in every list, Table, Detail
panel, and reference display.

An **info bubble** is the filled circular `?` beside a property. Its circle,
glyph, placement and interaction are shared. The bubble is centered horizontally
between the left edge of the property-label lane and the rendered right edge of
the property-name text; it is not merely centered in a generic metadata slot.
Its `?` glyph is optically centered inside the circle by the shared framework.

Info-bubble text explains **meaning and consequences**, not visible UI metadata.
It should tell a mod author what the property represents in the game/editor, what
changing it affects, non-obvious value semantics, important relationships with
other properties, or caveats that cannot be inferred from the label alone.

Never put the property's data type, allowed/storage numeric range, step size, displayed unit,
current value, or generic instructions such as `Set X`, `Edit X`, `Choose X`, or
`Enable/disable X` in an info bubble. Those facts are already represented by the
field and its metadata. If no useful semantic explanation is known, omit the info
bubble rather than filling it with tautological or storage-level text.

## Projects and Vanilla

The project selector lists Vanilla first, then editable mods. Vanilla is the
unchanged extracted baseline and is read-only. The first save from Vanilla asks
to create an editable mod. A new mod name can use a suggestion from
`ui/assets/mod_names.json`. Each editable mod row carries its own rename, open
folder and "what did Lexeditor find in this mod?" buttons; that report belongs
to the mod being pointed at, not to whichever mod happens to be loaded.

This workflow needs a game-specific baseline adapter because each game stores
and builds mods differently. A plugin must not call an editable working folder
"Vanilla" unless its data is proven unchanged.

## Developer Mode

Lexeditor has one privileged mode: **Developer Mode**. It activates automatically
only when the active GitHub CLI account is the authorized `Lexer-Lux` account and
is not a user preference. Developer Mode exposes diagnostics, the embedded GitHub
workspace, helper/version authoring, distributable defaults and shared layout
authoring. Signing out (or switching GitHub accounts) disables those privileges.
There is no separate Lexer Mode.

Holding right-click on a page tab to save its layout for everyone is therefore a
Developer Mode authoring action. Ordinary page and setting changes remain local.

## Model preview drawer

A Detail panel can declare an optional **model preview drawer**. The standard
header icon is its open control. Activating that icon slides the preview out from
the Detail panel; while open, an `×` occupies exactly the same header-icon slot
and closes it. Plugins provide only the preview content/lifecycle callbacks. They
must not invent a separate preview-panel type or a different close position.

## Setting dependencies

A setting can declare another setting as a requirement. Turning the requirement
off disables its dependents and remembers only the dependent values that this
action turned off. Turning the requirement on restores those remembered values.
A dependent that the user turned off manually stays off.

Hovering either related setting draws a semi-transparent flowing arrow from the
requirement control to its dependent control. This shows both what the setting
controls and what it requires without permanent connector clutter.


### Shared control spacing and hover behavior

- Every property carries a **type rail** just left of its name, whether or not
  it also has authored help. Pointing at the property brings its type code up;
  pointing at the rail itself replaces that code with the help marker, and only
  where there is one. A row of switches follows the same rule per switch.
- Revealing help is a pointer or keyboard-focus state, never a click state. A
  click that leaves focus on the marker must not hold the swap open after the
  pointer has left.
- A boolean's pin annotates the row, not the checkbox. It sits in the row's own
  right-hand corner, clear of the checkbox and of the reference mark beside it.
- The copy button is the whole width of its lane, so it centres by filling it.
  The lane is the button plus even air, never a wide column with the button
  pushed to one side of it.
- The divider between two panels is an edge, not a thumb in a track. At rest it
  is the hairline between the panels; pointing at it lights the whole edge and
  shows a pair of arrows saying which way it moves.
- A tab bar wraps only after tightening its tabs, and a bar that does wrap
  splits them as evenly as the count allows: seven tabs over three rows is
  three, two and two, never three, three and one.
- **A property's name is written for a person.** `State`, `Param1`, `Field03`
  and `Unknown` are storage labels, not names. A property whose only available
  name is the field it came from is a property nobody has finished yet; name it
  for what it does to the game.
- **A record's name is never also a property.** It is edited in the panel
  heading and in the table's own name column. A `NAME` row under a heading that
  already shows the name is the same value twice, and the copy being read is
  the one that cannot be changed.
- A column lights when its **header** is hovered. Hovering a cell lights that
  cell and its matching property, not the whole column: lighting the column
  from any row made simply reading down a table flash columns on and off.
- The pagination bar is one height on every page, whether or not it carries a
  search box.
- Text that can be followed is coloured like a link at rest, not only once the
  pointer is on it.
- A table cell centres its text by the glyphs, not by the line box, so a game
  font's own ascent and descent cannot push a column off-centre.
- Value boxes are square. One box shape for names and numbers alike, and a
  plugin theme may restyle it but never round only one kind.
- A panel ends where the pagination bar begins. The bar reserves its own
  measured height and nothing more, so the same bar sits the same way in every
  plugin.
- A value box holds a number even when it paints that number the way a player
  reads it. A box showing `50,000` is fifty thousand to its own slider, its
  bounds check and anything else that reads it.
- A flag box is as wide as the flag in it, so the space inside it is the same
  on the left and the right. The boxes sit on a column grid; the track decides
  where a box starts, not how wide it is.
- The grip between two panels is one slim bar that grows and takes the accent
  under the pointer.
- Responding to an edit costs the same on a large panel as on a small one.
  Work that reacts to a change is scoped to what changed: a rebuilt reference
  pillar is not a reason to re-measure the property names three panels away.
- Tab shortcut badges fit the tab height with a margin. The title reserves space
  on both sides, so the badge cannot cover the text.
- The detail sort marker stays centered in the left gutter. Boolean arrows keep
  their arrowhead attached to the line in both ordinary and tabbed panels, and
  the arrowhead sits inside the label so nothing clips its tip.
- Copy buttons occupy a grid column between the label and the value control.
  Every property control reserves that column, including the ones with nothing
  to put in it, so no control starts left of the column its neighbours start on.
- Every row of the mod menu uses one set of columns: mode, name, description,
  buttons, status. The name column is one width for the whole menu, so every
  description starts on the same edge and every status mark ends on the same
  one. A reference row holds the button lane it does not fill.
- Each mod row carries its rename, folder and contents-report buttons. They show
  a colored rounded hit area on hover or keyboard focus.
- Project actions read “➕ Add a Mod” and “🔍 Find a Mod”. Blank stores sample
  projects in browser storage; game plugins use their existing folder workflow.

Run `tests/control_layout_browser_check.py` for these rendered regressions at
1600, 1000, and 700 pixels. Routine pytest discovery is limited to `tests/`.
