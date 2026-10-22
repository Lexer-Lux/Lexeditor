---
name: ux-design
description: Lexeditor's screen layout and component rules: panels, previews, headers, lists, controls. Use before building or changing any editor screen, panel, preview, header, or shared control.
---

# UX design

Every screen in the editor answers the same three questions: what is selected
(left), what are its details (right), and what can I do with it (header).
These rules exist because each one was broken and reported at least twice.
When two screens show the same kind of data, they use one component and one
set of sizing rules. Fix that component and check each caller before adding a
screen override.

## Panels

- The left panel navigates: tabs and lists of things. The right panel shows
  the details of whatever is currently selected, nothing else. It never grows
  its own navigation tabs; the timeline's orange event markers, for example,
  select an event and the right panel shows that event.
- A panel tab with one list component and nothing else gives the whole tab,
  below the header, to that list. No wrapper div that insets it on three sides
  and strands half the tab empty below. The scroll wheel over the list flips
  pages.
- A tab with nothing to show is grayed out, shows the not-allowed cursor, and
  says why (for example, no record selected, or no records at all). A tab that
  looks clickable and does nothing is a bug.
- Divider positions are automatic: each panel takes the minimum size it needs
  and the layout divides what is left. They are never a setting, never saved,
  and never reset.

## Previews

- A property that points at a record in another tab shows a preview of that
  record whenever the target can be seen: model, texture, icon, sound row.
  The preview opens the target; a reference without one is missing a feature.
- A preview has three states: content, empty, and failed. Each looks different
  and says what happened.
- An empty preview is not clickable. No magnifier, no drawer, no new tab.
  Opening a larger view of nothing is a bug.
- Loading shows the shared centered throbber (`loadingPanel` /
  `loadingStatus`), never a per-screen spinner and never a white square where
  the preview will be.
- A larger view opens in the in-app drawer, never a browser tab.

## Headers

- A section with nothing in it, or one property, gets no header. A heading
  over a single row is clutter, and a heading the reader must delete by hand
  is a bug in the page, not a task for the reader.
- The detail header holds identity (name, kind, size) and the standard record
  actions: add, duplicate, delete. The add button lives here, once. A second
  add button appearing in the list panel on hover is a bug.
- The enable/disable switch is always the rightmost control in the header.
- Whatever the game lets a mod change is editable, names included. A stored
  name renames through `pagedListDetail`'s rename: the table's Name cell and
  the detail heading, by double-click. A page that cannot rename says why in a
  `// names:` comment above the call.

## Lists

- Identity stays in the master list; every editable field stays in the
  selected record's detail pane (`pagedListDetail`). The list never grows
  inline editors.
- A pager and a scrollbar never coexist on one list. The point where pages
  split is the point before a scrollbar would be needed. The pager bar looks
  the same everywhere, drop shadows included: one shared `pager`, fixed once.
- Every property of a list-and-detail page can be pinned as a table column.
  The framework adds the pins; rows carry the values (`row.values` /
  `row.display`), so a pinned column is never blank for a record that has the
  value.
- Loose table panels list their tabs alphabetically unless the game defines an
  order. Back returns to the exact subtab the reader came from, never the
  first subtab of the tab.

## Controls

- Use the most appropriate control for the value: checkboxes for booleans,
  bounded number controls for numeric ranges, selects for known enums. No free
  text or unbounded number input when the schema gives a finite choice or a
  valid range.
- A slider spans the whole accepted range of its property, from the game's own
  metadata (dev Minimum/Maximum tags). There is no second observed-maximum
  span: a slider that caps below the displayed maximum is a bug.
- Units come from the shared unit component: frames render as 𝑓 (U+1D453),
  percentages as a trailing `(%)`. A number with a unit never shows bare.
- Leading icons before properties come from the one global icon component
  (`iconValue`). A property whose concept has an icon (souls, stamina,
  reinforce, price, gems) shows it on every screen; a missing one is a bug,
  and a table guard test pins the known set.
- Vector properties (Rotation, Position, Scale) draw X, Y and Z on one row,
  always, with one shared column count across screens.
- Dropdown text scales to fit; it never clips or truncates. If the text cannot
  fit, the control grows or wraps, it does not cut words off.

## Words on the screen

Help bubbles follow the help-text skill: player terms, three sentences at
most, and only where the label and control do not already say everything.
Counts, coverage, limits, caveats and disclaimers belong in the panel's help
bubble, not in a paragraph on the page. A visible note is only for a state the
reader must act on now: an error, a missing file, an empty table.

## Verification

- Look at the rendered screen. Source, API and smoke checks never substitute
  for seeing it. One browser at a time, headless.
- Run only the one test file that covers the change. Full suites run on CI.
- Every global rule in this file has a guard in `tests/shared/` (for example
  `test_list_names_decided.py`, `test_no_tweak_payloads.py`). A new rule lands
  with its guard in the same change, or the next screen breaks it again.
