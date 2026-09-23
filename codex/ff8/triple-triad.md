# Triple Triad field opponents

`plugins/ff8/field_data.py` reads CARDGAME calls from field scripts. A call belongs
to a script entity. One entity can contain multiple calls, so call count is not
opponent count. The editor groups calls by map and entity. Identical entity
names in different maps do not establish that they are the same person.

SYM entity names are internal identifiers. They are not a complete catalogue
of displayed NPC names. Unresolved names must remain explicit; do not infer a
named character from an arbitrary entity code.

The documented argument order is deck ID, carried/known rules, region rules,
rare-card chance, and three unknown arguments. Rare-card chance is documented
as a percentage from 0 to 100. The final three arguments must not be labelled
as proven AI profiles or allowed card levels.

An argument can be a literal or a variable reference. The latter selects a
variable whose value is read during play; it is not the current match value.
Edits preserve the original argument opcode and unrelated script bytes.

Source: [CARDGAME opcode research](https://wiki.ffrtt.ru/index.php/FF8/Field/Script/Opcodes/13A_CARDGAME).
The documented meanings are not new in-game acceptance results.
