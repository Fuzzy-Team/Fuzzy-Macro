# Changelog

## Unreleased

- Run Roblox on a dedicated 1920x1080 virtual display (sRGB IEC61966-2.1, non-retina, 100% scaling) with a live preview window, based on [DeskPad](https://github.com/Stengo/DeskPad). Off by default; enable it in Config > Other > Virtual Display.
- Reject incomplete standby durations such as `30m 999` and `1h 30`, and report oversized durations without an integer-conversion error.
- Add standby usage to Discord command help and the README.
- Keep Eel callbacks responsive during standby and acknowledge stop requests so Start remains available.
