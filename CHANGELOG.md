# Changelog

## Unreleased

- Preserve saved movement speeds and hotbar slots during upgrades, including numbers with leading zeros.
- Keep the camera steady when restoring Shift Lock after using the inventory, and prevent inventory cleanup from re-enabling it after gathering ends.
- Resume backpack and balloon conversion when a suspected night is not confirmed.
- Respond to pause, stop, and skip requests while searching for the cannon, and release held movement keys when interrupted.
- Open the GUI without loading text recognition until it is needed.
- Read recurring settings faster and reuse compiled gather patterns while still picking up edits during a gather.
- Report settings that could not be saved and restore their saved values in the GUI.
- Show saved dropdown values even when their options are missing, and use built-in defaults for unsaved settings.
- Keep macro hotkeys inactive while recording a keybind.
- Confirm night at the hive before hunting the Vicious Bee, improve hive claiming, and adjust drift correction to the field size.
- Use the configured gumdrop and Glitter slots consistently, including inventory Glitter for slot 0, while keeping separate AFB and TAD alt slots.
- Reduce download size and startup work by removing unused dependencies and assets and sharing notification text recognition.
- Reject incomplete standby durations such as `30m 999` and `1h 30`, and report oversized durations without an integer-conversion error.
- Add standby usage to Discord command help and the README.
- Keep Eel callbacks responsive during standby and acknowledge stop requests so Start remains available.
