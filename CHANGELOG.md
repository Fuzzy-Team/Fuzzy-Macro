# Changelog

## Unreleased

- Track special planter route growth using saved active macro runtime. Stop, pause, standby, reconnect, and app downtime do not advance growth. Existing wall-clock route timers restart conservatively; reward cooldowns remain based on calendar time.
- Reject incomplete standby durations such as `30m 999` and `1h 30`, and report oversized durations without an integer-conversion error.
- Add standby usage to Discord command help and the README.
- Keep Eel callbacks responsive during standby and acknowledge stop requests so Start remains available.
