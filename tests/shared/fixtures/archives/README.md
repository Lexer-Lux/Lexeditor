# Archive reader fixtures

The small `.rar.uu` fixtures come unchanged from
[libarchive 3.8.11's format tests](https://github.com/libarchive/libarchive/tree/03036ffa409a2aa1c5bbad35be2202641a040fda/libarchive/test).
Their names identify the original upstream cases. They exercise actual RAR3,
RAR5, solid archives, Unicode paths, links and malformed/encrypted inputs.
They are ASCII uuencoded data; tests decode them only inside their temporary
directories. Libarchive's copyright and BSD redistribution notice is included
in `assets/helpers/libarchive/licenses/libarchive.txt`.
