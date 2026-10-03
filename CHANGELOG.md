# Changelog

## Unreleased

- Reject incomplete standby durations such as `30m 999` and `1h 30`, and report oversized durations without an integer-conversion error.
- Add standby usage to Discord command help and the README.
