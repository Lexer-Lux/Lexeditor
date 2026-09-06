# GitHub #118 - Mounted camera stuck above horse

## 2026-08-10 actual repair after false implementation record

The earlier worklog claimed `horse_camera.cpp` had a repaired input-yielding
controller and that `verify_horse_camera_issue_118.py` checked it. Neither claim
matched the workspace: the module was an inert stub and that verifier did not
exist. Reintroducing the ASI heading/pitch writer would also revive the exact
camera fight that produced the stuck/jumping result.

The relevant live requirement is #47, whose body explicitly authorizes
installing Riyusso's existing **Disable Horse Camera Centering** mod if it still
works. The already-downloaded, credited release was installed as its own LML
replacement at `lml/Disable Horse Camera Centering`. Its `cameras.ymt` SHA-256
is `1C5C4064A105A4E596A62678A818446D2BC2B8D2810113E9E6F8AF9A8E367273`.
The installed `install.xml` targets exactly
`update:/x64/data/metadata/cameras.ymt`.

The mounted record `0x95DDC7CB`, block `0x8C427004`, contains the four verified
reference values: `0x791B55E6=0`, `0xFB0803FA=0`, `0xF82ED670=3000`, and
`0x1AAAAB19=1`. The ASI horse-camera module remains inert and contains no
relative-heading/pitch getter or setter.

`verify_horse_camera_issue_118.py` now exists and passed against the installed
payload, exact record values, replacement target, pinned file hash, and absent
ASI orbit writer. RDR2 was already running when the LML files landed, so the
remaining acceptance begins on the next full launch: mounted mouse/controller
orbit must move immediately, remain where released, and preserve aim, Look
Behind, first person, cinematics, and dismount transitions.

## Symptom

While mounted, the ordinary third-person camera was pinned above the horse and
did not respond to camera movement.

## Cause

The #47 anti-centering controller re-anchored its stored heading and pitch and
called both camera setters during the same frame in which it detected look
input. ScriptHook can run before Rockstar finishes applying that frame's camera
input. In that ordering, the getters still returned the old orbit and the
setters restored it, so the player never received a setter-free frame in which
to move the mounted camera. The previous worklog explicitly left frame ordering
as an unresolved runtime boundary; #118 demonstrated the bad ordering.

PAD normals can also be consumed by a mounted camera context before the ASI
observes them. Relying on those values alone made controller yielding fragile.

## Fix

`modules/horse_camera.cpp` now returns without calling either camera setter for
every frame with real look input. It marks the held orbit invalid, then captures
the resulting Rockstar camera on the first frame after input release. Only idle
frames restore that captured orbit to reject automatic recentering.

The input test retains enabled/disabled PAD normals for mouse, remapped input,
and non-XInput controllers, and adds the physical XInput right stick with its
native deadzone as a fallback. No sensitivity, acceleration, or inversion is
reimplemented.

The existing exclusions for aiming, first person, cinematic camera, gameplay
hints, Look Behind, player-control loss, and unmounted states remain intact.

## Static verification

`python tools/reverse-engineering/verify_horse_camera_issue_118.py` checks that
look input returns before either setter, that post-input capture exists, that
the physical right-stick fallback is present, and that all camera exclusions
remain.

## Runtime acceptance boundary

After integration/build/install, mount a horse and move the ordinary
third-person camera through broad horizontal and vertical arcs using both mouse
and controller. It must move immediately and remain where released instead of
snapping above/behind the horse. Also verify aim, Look Behind, first person,
cinematic/scripted cameras and dismount transitions remain vanilla. Static
checks cannot establish ScriptHook-versus-camera frame order in the live game.
