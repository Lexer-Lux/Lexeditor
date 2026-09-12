# Why FINAL FANTASY VII REMAKE is 101 GB, and whether a button can fix it

Measured on this machine, 2026-09-09, against the real install at
`D:\SteamLibrary\steamapps\common\FINAL FANTASY VII REMAKE`. Read with
Lexeditor's own PAK reader, so this is the archive index, not a guess.

## Where the space goes

| Part | Size |
| --- | --- |
| `.pak` archives (25 files) | 78.8 GB |
| `.emov` prerendered video | 22.5 GB |
| Executables and libraries | 0.12 GB |
| **Total** | **101.4 GB** |

Inside the archives, 961,697 entries:

| Content | Stored |
| --- | --- |
| `.ubulk` (texture and mesh bulk data) | 48.0 GB |
| `.uexp` (asset payloads) | 29.5 GB |
| `.uasset` (headers) | 0.47 GB |
| everything else | under 0.1 GB |

## The compression answer, which is no

925,885 of the 961,697 entries are already Oodle-compressed. Together they
store 78.0 GB of data that is 206.4 GB raw - the archives are already at 37.8%
of their uncompressed size, using one of the best general-purpose compressors
shipped in games.

The 35,812 entries stored uncompressed hold 0.01 GB between them. Recompressing
every one of them perfectly saves under ten megabytes of a hundred gigabytes.

So a "make my game smaller" button that recompresses the PAKs cannot work.
There is nothing left to squeeze. Anything that claimed otherwise would be
repacking 78 GB to save nothing, at the cost of hours of disk churn and a game
that no longer matches its Steam manifest.

## Why it feels wrong

The observation that the textures do not look like 100 GB of textures is fair,
and the reason is not compression:

- **22.5 GB is video.** Nearly a quarter of the install is prerendered cutscene
  movies, which do not improve any texture you look at while playing.
- **48 GB is bulk data**, and Unreal ships full mip chains plus platform texture
  formats. A low-quality-looking texture and a large texture are not opposites;
  an upscaled PS1-era asset stored as a 4K BC7 mip chain is both.
- The game ships one build for every GPU, so nothing is trimmed for the machine
  it lands on.

## What could actually reclaim space

These are real, and none of them is a safe one-click button:

1. **Deleting or stubbing unused language audio and video.** Tens of gigabytes,
   reversible only by re-downloading, and it breaks the Steam file check.
2. **Re-encoding `.emov` video.** Where the gigabytes are, but it is
   transcoding: quality loss, long CPU time, and the engine expects that
   container.
3. **Dropping the top texture mip.** Halves texture memory for a visible
   quality cost, and needs every affected `.ubulk` rebuilt.

Each of those changes what the game ships, not how it is packed. If Lexeditor
ever offers one it should be a considered, reversible, clearly-labelled mod -
not a button called "compress".
