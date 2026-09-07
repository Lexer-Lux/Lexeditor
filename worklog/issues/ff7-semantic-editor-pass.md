# FF7 semantic editor pass

The FF7 editor must expose game concepts rather than binary storage representation.

Scope: every currently exposed FF7 numeric field is classified as one of:

- a genuine numeric gameplay value, with an explanation/unit;
- a named enum/select;
- a named bitflag/checklist;
- a reference to another FF7 dataset, shown by record name;
- a compound encoded value with a semantic editor; or
- explicitly advanced/engine data when no authoritative semantic mapping is available.

Raw IDs, masks and bytes must not appear as ordinary first-class controls when a human mapping exists. Unknown/modded values must be preserved rather than coerced.
