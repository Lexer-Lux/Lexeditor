# Update Lexeditor

Select **UPDATE** at the bottom right of the main menu. Lexeditor checks the latest
stable GitHub release. If a newer release is available, select **INSTALL**.
Save or discard editor changes first. Lexeditor closes, installs the release,
checks startup and opens again. Updates do not start without this action.

The updater supports the current Git source installation. Git must be available.
It uses the published release tag, not the latest `master` commit. An install ahead
of that release is left unchanged. Source edits and separate local commits also
block replacement. This does not update game helpers.

Git updates only tracked application files. Ignored projects, settings, game data
and other untracked files are preserved. A conflicting untracked file blocks the
update. Changed Python requirements are installed with the app's current Python.

The previous source commit is kept under `refs/lexeditor-backups/`. If the startup
check fails, the updater restores that source and reinstalls its requirements.
Rollback refuses to discard source edits made by another process. The next launch
shows the update result. Details remain under `%LOCALAPPDATA%\Lexeditor\updates`.

Automated tests use temporary Git installs and a headless browser. They do not
claim that a native window has closed and reopened on a user's desktop.
