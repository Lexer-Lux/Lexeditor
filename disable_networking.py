"""Distribution setting. Restart Lexeditor after editing this file.

GitHub releases leave the final string empty. Nexus releases copy
NEXUS_DISABLED_TEXT into that string as a quoted literal, using
python tools/configure_nexus_networking.py PATH_TO_RELEASE --nexus.
"""

NEXUS_DISABLED_TEXT = """Do not edit any part of this string and then press Save, or network features will be re-enabled.
This distribution of Lexeditor has external networking disabled. Nexus Mods' file submission rules restrict internet communication and explicitly exclude automatic updates from the essential-function exception. This means this copy cannot check for or download application updates, download mods, or retrieve other online content. Local editing and communication between the editor and its local game services remain available.
The GitHub distribution does not have this restriction. The source code is editable: changing any character in the separate quoted setting below, saving the file, and restarting Lexeditor re-enables its network features. There is no network switch in the application's settings. Keep this notice intact in the Nexus distribution so its behavior and the reason for that behavior are visible to users. If you disagree with the restriction on automatic updates, you can write to Nexus Mods support and ask them to reconsider it. Opening a draft never sends the email automatically.
Do not edit any part of this string and then press Save, or network features will be re-enabled."""

DO_NOT_EDIT_ANY_PART_OF_THIS_STRING_AND_THEN_PRESS_SAVE_OR_NETWORK_FEATURES_WILL_BE_RE_ENABLED = ""


def disabled():
    return DO_NOT_EDIT_ANY_PART_OF_THIS_STRING_AND_THEN_PRESS_SAVE_OR_NETWORK_FEATURES_WILL_BE_RE_ENABLED == NEXUS_DISABLED_TEXT
