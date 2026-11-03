# Offline archive reader

Libarchive 3.8.11 reads mod archives locally, including RAR, RAR5, 7z,
ZIP/ZIPX, TAR with gzip/bzip2/xz/zstd, CAB, LHA, XAR and CPIO.

This Windows x64 DLL was built by Lexeditor's **Build archive reader** CI
workflow from the upstream and vcpkg commits recorded in `manifest.json`.
`tools/build_archive_runtime.py` reproduces the build. It uses Windows CNG
and XML APIs and statically links zlib, bzip2, liblzma, LZ4 and Zstandard.
No external unpacker, compiler, installation step or network connection is
needed when a player imports a mod. Password-protected and split-volume
archives require additional support and are reported as import errors.

Upstream: <https://github.com/libarchive/libarchive/tree/03036ffa409a2aa1c5bbad35be2202641a040fda>

Python bindings: <https://github.com/Changaco/python-libarchive-c>

Copyright and redistribution terms for the library and its codecs are in
`licenses/` and in Lexeditor's Credits screen. The Python binding is CC0.
