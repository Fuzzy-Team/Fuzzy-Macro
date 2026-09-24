# Test checklist: perf-dependency-cleanup (PR #80)

Changes this branch adds on top of `combined-improvements`.

## Install script
- [ ] Run `install_dependencies.command` on macOS 10.15–11 (Intel). It should still finish, and `Polygon3` is no longer installed.
- [ ] Run the installer on an existing install and check that it finishes without errors.

## Settings and profiles
- [ ] Change a profile setting in the GUI (e.g. a toggle on the Macro tab), restart the GUI, and confirm it saved.
- [ ] Change a general setting (e.g. Discord/webhook settings), restart, and confirm it saved.
- [ ] Change field settings (pattern, size, etc.) for an enabled field, restart, and confirm they saved.
- [ ] Import field settings / a profile JSON and check the values apply (bulk profile saves now go through the store directly).
- [ ] Enter an invalid value (e.g. text in a number box). The GUI should show an error, not crash or save garbage.
- [ ] Switch profiles in the GUI and check each profile keeps its own settings and field list.
- [ ] **Export a profile** (current and a non-current one). The exported JSON should include settings, general settings, and fields, and must NOT contain `discord_bot_token`, `webhook_link`, or `private_server_link`.
- [ ] Old profile with a setting saved in the wrong file (e.g. a profile setting in `generalsettings.txt` that you changed from its default): after loading/exporting, your changed value is kept, not the default.
- [ ] Settings or field names with non-ASCII characters save and reload unchanged.
- [ ] Export a profile whose files are corrupted or missing. You should get an error message and no crash.

## Running macro
- [ ] Start the macro and, while it runs, change a setting in the GUI. The macro should pick it up on the next loop (settings now reload once per loop from one profile snapshot, not from a 0.5s cache).
- [ ] Enable quests with a quest that turns on a task you have disabled (e.g. a mob kill quest). Once the quest is done, the macro should stop running that task (quest-enabled flags now reset every loop pass).
- [ ] Switch profile while the macro is stopped, then start it. It should use the new profile's settings and fields.
- [ ] Pause/resume during a gather pattern and a task that sleeps. Pausing should still hold the sleep (`pauseable_sleep` is now an alias of `sleep`).

## Gathering
- [ ] Gather with a built-in pattern for several cycles. It should behave the same (the shipped pattern file is now read once per gather session).
- [ ] Gather with a custom or edited pattern. It should still be treated as custom.
- [ ] Edit a built-in pattern file while the macro is gathering with it. The next cycle should run your edited file.

## Hive claiming
- [ ] Start the macro with a free hive slot. It should claim the hive (normal detection).
- [ ] Start with your preferred slot taken. It should fall back to another slot or report no claimable hive, and the log should make sense.

## Reports
- [ ] Hourly report still generates and looks the same (dead code after the report `return` was removed).
- [ ] Final session report still generates.
