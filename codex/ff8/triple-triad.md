# Triple Triad field opponents

`plugins/ff8/field_data.py` reads CARDGAME calls from field scripts. A call belongs
to a script entity. One entity can contain multiple calls, so call count is not
opponent count. The editor groups calls by map and entity. Identical entity
names in different maps do not establish that they are the same person.

SYM entity names are internal identifiers. They are not a complete catalogue
of displayed NPC names. Unresolved names must remain explicit; do not infer a
named character from an arbitrary entity code.

The argument order is deck ID, match rules, trade rule, rare-card chance,
two unknown arguments, and the common-card level mask. The earlier labels
"Known rules" and "Region rules" confused script inputs with regional save
state: argument 3 is the trade rule, not a second rule mask.
Rare-card chance is a percentage from 0 to 100. The two unresolved arguments
must not be labelled as proven AI profiles.

## Match rules

In the supported executable, CARDGAME stores argument 2 at `0x1DCD7A8` and
argument 3 at `0x1DCD7AC`. Initialization at `0x534350` copies these to the
active rule mask (`0x1DCD794`) and trade byte (`0x1DCD766`). Rule consumers
test the low mask bits; for example `0x539E56` tests Open, `0x53A6E7` tests
Elemental, and `0x53AD1D` tests Plus. Higher script flags are preserved.

The low bits, in order, are Open, Same, Plus, Random, Sudden Death, unused
Retry, Same Wall and Elemental. Trade values 0–4 are None, One, Difference,
Direct and All. This matches the independent
[Hyne rule controls](https://github.com/myst6re/hyne/blob/master/src/PageWidgets/TTriadEditor.cpp).
Only established rule bits are editable. Retry remains unchanged.

Variable-mode arguments contain references, not current rule values. For
example Balamb Garden students pass variables 292 and 293 for the two inputs.
The static editor must not display reference 292 as if it were a rule mask.

## Common-card pool

For the supported English executable (SHA-256
`064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570`),
CARDGAME at `0x5225A0` pops argument 7 into `0x1DCD7B0`. Hand generation at
`0x537640` treats the low seven bits as levels 1–7. A zero byte falls back
to level 1. Each level contains eleven consecutive card IDs; PuPu (47) is
explicitly excluded. Common cards are drawn without duplicates until five
cards are present. The upper bit has no established meaning and is preserved.

`tests/ff8/verify_ff8_card_hand_levels.py` executes this native hand builder
under Unicorn with only its RNG replaced. It checks all 128 level masks,
including the zero fallback, five distinct cards, and the PuPu exclusion.
It reads the private installed EXE and does not redistribute it.

The deck ID is compared against rare-card ownership in save-state memory;
it does not index a fixed five-card list. The common-card levels can differ
between opponents that pass the same deck ID. A pool preview must therefore
use the selected CARDGAME call's level mask. The exact hand and available rare
cards depend on match-time state, so a static editor must not invent them.

## Rare-card ownership and selection

The native hand builder receives the side and deck ID. Deck zero skips rare
selection. For a nonzero deck, it compares all 33 ownership bytes at
`0x1CFEF85` against that ID. Index 0 is card 77, and index 32 is card 109.
These bytes share the card inventory array at `0x1CFEF38`; rare cards use an
owner byte where common cards use a count/seen byte. They are mutable save
state, not an executable table of five-card decks.

Matching rare cards are considered in ascending card-ID order. A candidate
succeeds when the native RNG result modulo 100 is less than the rare-card
chance. After the first success, each remaining candidate uses half the
original chance, rounded down; the chance does not halve again on each
success. Selection stops at five cards. The common-card builder fills any
remaining slots.

`verify_ff8_card_hand_levels.py` executes the actual supported routine for all
33 rare cards and all 256 ownership byte values. It checks zero chance,
deck zero, mismatched ownership, unchanged ownership state and the strict
percentage boundary. A controlled multi-card case proves the ordering,
five-card limit and half-chance rule. Only RNG is replaced. This is native
execution evidence, not a live match acceptance result.

The initial ownership is code, not a stored card-list table. After loading
`init.out` into the GF/start-data records, `0x56DA10` calls the separate card
initializer at `0x8DFF20`. It clears common-card counts and assigns rare cards
77–109 to owners 200–232 respectively. The same focused verifier executes
this initializer and checks all 33 assignments, common-card counts, the return
stack and adjacent state. Editing `init.out` cannot change these assignments:
they are made afterward. A modded starting assignment requires a guarded
Hext change to the card initializer; existing saves retain their current
owners unless another proven path changes them.

An argument can be a literal or a variable reference. The latter selects a
variable whose value is read during play; it is not the current match value.
Edits preserve the original argument opcode and unrelated script bytes.

Source: [CARDGAME opcode research](https://wiki.ffrtt.ru/index.php/FF8/Field/Script/Opcodes/13A_CARDGAME).
The documented meanings are not new in-game acceptance results.
