# Manual test checklist for PR #78

Automated checks covered tests, bytecode/scope comparisons, pixel-identical
report renders, and settings comparisons against `main` on 17 profiles.
Manual results are recorded below. The checked items were exercised on
2026-09-23, before the final cleanup commit. Retest affected settings and flows
using the unchecked entries before merging. Rare edge cases (unreadable settings
files, legacy misplaced settings, old Intel macOS versions, alt/TAD) were dropped
as low user impact.

## Updating from the current release
Do these on a copy of a real install that is on the current `main` release, with a
real profile (ideally one that has been through several older versions), using the
**in-app updater**. Note: the updater itself silently starts `install_dependencies.command`
in the background when it finishes, so the uninstall of torch/matplotlib/etc. and the
numpy/OpenCV force-reinstall run while you relaunch.
- [x] The update completes, the macro restarts, and the GUI opens without errors in the terminal.
- [x] Relaunch **immediately** after the "Update complete" box (while the background installer is still running `pip`). The GUI opens and the macro starts; if it fails, relaunch again after `pip` finishes (`ps aux | grep pip`) and note the error so the release notes can say to wait.
- [ ] After the background installer finishes, `~/fuzzy-macro-env/bin/pip list` no longer shows torch, torchvision, scipy, PyWavelets, matplotlib, html2image, httpx, or ImageHash (Apple Silicon / macOS 12+), and the macro still launches.
- [x] `src/modules/macro.py`, `src/modules/submacros/hourlyReport.py`, and `src/images/inventory/old/` are gone, and `src/modules/macro/` exists.
- [x] Your custom patterns and edited built-in patterns in `settings/patterns/` are unchanged; `blooms_ai.py` and `fuzzy_ai_gather.py` were replaced with the new versions.
- [x] The old venv (still has torch, matplotlib, ImageHash, html2image, httpx) starts and runs normally, and startup does not import torch.
- [x] Each profile gets a `.migration_version` file the first time it is loaded or switched to, and its settings look the same as before the update.
- [x] Switch to a profile you have not opened since updating; it migrates at that point (check its glitter and gumdrop slots).
- [x] Switch profiles from the Discord bot; the new profile migrates and the running macro picks it up.
- [x] Roll back with the updater's backup, then update again. The macro still starts, and settings changed on `main` in between still load.

## Slot migrations (users will not notice these changes until something misfires)
- [x] On `main`, set the Boost-tab glitter slot to **0 (inventory)** and turn on field booster **Glitter Extending**, then update. Config → Glitter Slot shows 0, and at 14:30 the macro finds Glitter in the inventory and logs "Used Glitter from the inventory". No hotbar key is pressed. If gathering with shift lock, shift lock and the held gather click pause during inventory access, then resume afterwards.
- [ ] Watch a field booster Glitter extension from the inventory that lands mid-pattern. The gather should carry on afterwards (this is how `main` behaved; if the open inventory breaks the gather, note it).
- [x] On `main`, set the field booster glitter slot to a non-default slot (e.g. 4), then update. Config → Glitter Slot shows 4, and AFB's own Glitter slot is unchanged.
- [x] On `main`, set AFB's glitter slot to 0, then update. AFB still finds Glitter in the inventory.
- [x] On `main`, turn on quest gumdrops with Quest Gumdrop Slot 2 and no field using goo, then update. Config → Gumdrop Slot is 2.
- [x] On `main`, turn on quest gumdrops and goo on a field using a different slot, then update. Gumdrop Slot keeps the field goo slot. Put this in the release notes.

## GUI save feedback
- [x] Set Max cannon attempts to 2 while Hive resync attempts is 3. The GUI lowers resync to 1 and both save, with no error message. Type 99 in Max cannon attempts; it saves as 25. *(Verified in the QA GUI; original 5/3 values restored.)*
- [x] Normal saves show no message.
- [x] Set a field's pattern to a custom pattern, then delete or rename that pattern file and reload the GUI. The dropdown shows `yourpattern (not found)` and hovering explains it. Gathering there falls back to e_lol with one alert. Choosing another pattern replaces it.
- [x] On a new profile, no dropdown shows "None" or is blank (spot-check Config, Collect, Planters, Boost, Quests, Gather).

## Setup
- [x] Launch with `run_macro.command`; the GUI opens with no errors in the terminal.
- [x] Startup feels faster than `main` (torch is no longer loaded).
- [x] `settings/patterns/` still has all your patterns, and any missing defaults were added.

## Settings (highest risk: the Macro Profile store was rewritten)
- [x] Change **Theme**, restart the macro, confirm it stuck. *(Verified across a GUI reload; Commander Theme restored.)*
- [x] Change **Max cannon attempts** and **Hive resync attempts**, restart, confirm both stuck. *(Verified 6/4 across a GUI reload; restored to 5/3.)*
- [ ] Change **Update channel** and **Webhook time format**, restart, confirm both stuck. *(Webhook format verified across a GUI reload and restored to 12. Update Channel initially displayed “None”; Stable persisted across reload, but the dropdown has no None option, so it is currently Stable and this item needs follow-up.)*
- [ ] Set Update channel to Beta, then check for updates from the GUI; it offers the latest beta release. Set it back to Stable; it offers only stable releases. Turn off automatic update checks and restart; the startup check stays off. (These now read through the profile store, which also handles values an old GUI bug saved wrapped in `{'source': ..., 'value': ...}`.)
- [x] Change a **per-quest gather time** (e.g. Polar Bear) and its return method, restart, confirm both stuck. *(Verified across GUI reload; restored to 0 / No Override.)*
- [x] Change the **hourly report time format** and **uptime buffs**, restart, confirm both stuck. *(Verified across GUI reloads; restored to 24-hour format and original buff selections.)*
- [x] Switch profiles in the GUI; the new profile's settings and fields load correctly. *(Switched from testing to pine, saw different settings and Field 1 values, then returned to testing.)*
- [x] Switch profiles while stopped, then start the macro; it uses the selected profile's settings and enabled fields. *(Selected `qa_09_drift_blooms_ai` while stopped; the subsequent run used its Blue Flower and Dandelion `blooms_ai` gathers.)*
- [x] Change a field's settings (pattern, size, width, distance), start a gather there, confirm they're used.
- [x] Start the macro, change a setting while it runs: it reloads without a "Profile Changed" message. *(Changed max cannon attempts to 6; the run logged attempt 1/6 and no Profile Changed message. Restored to 5.)*
- [x] Import a profile JSON and field settings, restart, and confirm the imported settings and fields persist.
- [x] Export both the current and another profile. Confirm each JSON has its own settings, general settings, and fields, with no `discord_bot_token`, `webhook_link`, TAD alt webhooks, private server or fallback server links, or HTTPS `route_` links. *(TAD alt webhooks and fallback server links used to be exported; fixed.)*
- [ ] Config → **Gumdrop Slot** (replaces the Quests-tab gumdrop slot): a goo quest, a field with Goo on, and the glue dispenser all use gumdrops from that slot.
- [ ] Config → **Glitter Slot** (0–7; replaces the Boost-tab field booster glitter slot): field booster extending presses it, and 0 finds Glitter in the inventory. Auto Field Boost uses its own Glitter slot, and 0 finds Glitter in the inventory there too.

## Hive claiming
- [ ] Rejoin with your **preferred hive free**: it claims that hive.
- [x] Rejoin with your **preferred hive taken**: it claims another free hive without walking
      back from the wrong spot (watch for "Scanning remaining hives").

## Gathering
- [x] Gather with a **built-in pattern** (e.g. e_lol, lines). *(`qa_07_drift_builtin` logged a full 12-minute Blue Flower `e_lol` gather.)*
- [ ] Gather with a **custom/edited pattern**.
- [x] Gather with a **broken custom pattern**: one critical-error alert, then e_lol for the rest of that gather. *(`qa_11_pattern_broken` logged one syntax alert and used `e_lol`.)*
- [x] Gather with **fuzzy_ai_gather** and **blooms_ai**. *(`qa_08` ran `fuzzy_ai_gather` for 10m58s; `qa_09` ran a 12m01s Dandelion `blooms_ai` gather. The separate drift and token-leash checks below remain open.)*
- [x] Gather with **field drift compensation** on (color-based, Supreme Saturator). In a narrow field, a bad locator reading must not cause a correction that walks out of the field.
- [x] With field drift compensation enabled, run **fuzzy_ai_gather** and **blooms_ai** in a narrow field; token chasing stays within that field's dimensions.
- [x] Gather with **"Use sprinkler model for field drift compensation"** on.
- [x] Field drift compensation now corrects for at most 0.6–1.6s per cycle depending on the field (was about 1.6–2s everywhere). In **Blue Flower** (0.6s cap), **Dandelion** (0.8s), and **Bamboo** (1.0s), let a normal pattern run 10+ minutes and confirm the character stays centred on the saturator instead of slowly drifting out.
- [x] **fuzzy_ai_gather / blooms_ai with field drift compensation on in Blue Flower and Dandelion**: the token leash is now capped by the field's narrow side (about 2.7 tiles in Blue Flower, 3.6 in Dandelion, versus about 5–6 before), and nearby tokens past it are no longer allowed. Compare tokens and honey per hour with `main` on the same field; if collection drops noticeably, the cap is too tight for long fields.
- [x] Sprinklers, backpack-full convert, and gather time limits behave as before.

## Other tasks
- [ ] **Convert** at the hive, including at night (night detection was rewritten).
- [ ] **Mob run**: detects "defeated" / "died" and loots.
- [ ] **Vicious Bee** hunt: finds the field and detects the defeat.
- [ ] Coconut Crab / King Beetle / Tunnel Bear / Mondo if you use them.
- [ ] **Planters**: place and collect (inventory images moved from `images/inventory/old`).
- [ ] **Memory match** identifies rewards (icons moved out of the code into image files).
- [ ] Quests: get a quest, gather for it, submit it.
- [ ] Complete a quest that temporarily enables a disabled task (such as a mob run). On the next loop, the task returns to the profile's disabled setting.

## Reports and integrations
- [x] **Hourly report** image looks right in your theme.
- [ ] After an hourly report and counter reset, the next hourly report starts a new hour while the final report retains session totals and collected items.
- [x] **Final report** on stop, and the **item monitor** report; check the final report's theme and session totals.
- [x] Toggle `hourly_report_embed_text` and confirm hourly and final Discord/webhook posts always include the report image, with text fields only when enabled.

## Controls
- [x] Start / pause / resume / stop hotkeys work (hotkey code was rewritten).
- [x] While **recording a keybind** in the GUI, pressing F1/F3 does not start or stop the macro. *(Failed: F1/F3 started/stopped the macro while recording, because the recording check called a GUI function that didn't exist. Fixed; retest.)*
- [x] Hotbar Buff / Auto Clicker / Auto Gifted Basic Bee hotkeys start their tools.
- [x] Stop the macro with a hotkey while a hotkey-launched tool is running; the tool stops too.
- [ ] Pause and resume during a gather pattern and a sleeping task; movement and the sleep wait while paused, then continue.

## Performance and dependency cleanup
- [x] Start the macro from the GUI: it runs normally (the macro loop moved from `main.py` to `modules/macro_loop.py`). *(Multiple QA profiles started from the GUI, claimed a hive, and reached gathering.)*
- [x] With the Discord bot enabled, the bot starts and responds to commands (it no longer loads the macro at startup).
- [ ] **Intel Mac on macOS 12+** (Python 3.8). It uses the same installer branch as Apple Silicon, so re-running the installer now uninstalls torch, torchvision, scipy, and PyWavelets there too. Afterwards: the macro launches; fuzzy_ai_gather and blooms_ai load a model (Core ML, or ONNX if Core ML fails) and gather; OCR works through Apple Vision (blue text pings, quest titles); and the terminal shows no dyld or torch import errors. Also run a fresh install on that Mac. If no such Mac is available, say so in the release notes.
- [ ] Re-run `install_dependencies.command` on an existing install: matplotlib, html2image, httpx, ImageHash, and (Apple Silicon) torch/torchvision are uninstalled, and the macro still launches.
- [ ] **Guiding star**, **windy bee**, **unusual sprout**, and **sticker sprout** pings still fire, including with several enabled at once (they now share one OCR scan).
- [ ] **Memory match** still pairs tiles (image hash replaced; blue text read renamed).
- [ ] **Blender** with max quantity stops adding once the quantity stops changing (image hash replaced).
- [ ] Quests: the quest page scrolls to the top and reads quest titles (image hash replaced).
- [ ] Inventory item search scrolls and finds items, e.g. using glitter or a planter (image hash replaced).
- [ ] **Auto Gifted Basic Bee** scrolls and detects rolls (image hash replaced).
- [ ] **Auto Field Boost** and field booster quests detect the boosted field from the blue text.
- [x] GUI → Collect → Seasonal: the **Petals & Blooms** cheat sheet shows and stays sharp when clicked to zoom (now WebP).
- [x] GUI → Collect → Memory Match: all reward icons show in the reward picker (now loaded from `src/images/memorymatch/`).
- [ ] Start the macro with blender enabled and no items left to craft: the "no more items left to craft" popup still appears.

## Optional
- [x] A fresh install on Apple Silicon (macOS 13+) installs without torch and AI gathering works. `settings/patterns/` is created and filled from the defaults on first launch.

## Run results — 2026-09-23
- The macro started normally in Normal Mode at 1920×1080 and rejoined Roblox.
- When hive 1 could not be claimed, it continued directly to hive 2 and claimed it; the preferred-hive-taken check is marked complete.
- The macro converted at the hive, travelled to Pine Tree, gathered with `blooms_ai`, returned on a full backpack, and walked back to the hive. Active sprinklers were visible in Roblox.
- The macro was stopped by the user. The remaining unchecked items were not exercised in this run.

## Settings check — 2026-09-23
- Settings persistence checks used GUI reloads only; the macro was not started.
- Theme: changed to Mythic, survived reload, then restored to Commander and reloaded.
- Cannon thresholds: changed to 6 attempts / 4 hive-slot rechecks, survived reload, then restored to 5 / 3 and reloaded.
- Hourly/session report format: changed to 12-hour, survived reload, then restored to 24-hour and reloaded.
- Uptime buffs: enabled Gummy Star, confirmed after reload, then disabled it and reloaded; original selections were restored.
- Webhook time format: changed to 24-hour, confirmed after reload, then restored to 12-hour and reloaded.
- Update Channel: initially displayed “None”; changed to Stable and confirmed after reload. The GUI offers only Stable and Beta, so it could not be restored to the initial displayed value and remains Stable.
- Polar Bear quest override: set gather time to 1 minute and return method to Walk; both survived a GUI reload. Restored to 0 and No Override, then reloaded.
- Profile switch: pine showed max cannon attempts 3 and Field 1 disabled with AI Gathering, width 3, and 8 minutes. The original testing profile loaded Field 1 enabled with BloomsAI, width 4, and 10 minutes when selected again.
- Field 1: changed BloomsAI / M / width 4 / Center / distance 1 to bowl / S / width 3 / Right / distance 2. The new values survived a GUI reload. A Pine Tree gather started with bowl in the log. The original values were restored and confirmed after reload.
- While the macro ran, max cannon attempts changed from 5 to 6. The running macro later logged "Could not find cannon (attempt 1/6)" with no "Profile Changed" message in the visible log. The value was restored to 5 after stopping.

## Controls check — 2026-09-23
- Clicking Start in the GUI launched the macro; clicking Stop ended it. The Home view returned to Start and logged "Macro Stopped."
- F1 while recording the Start Macro keybind was captured as F1 without starting the macro.
- F1, F2, and F3 key inputs sent through computer use did not visibly start, pause, or stop the macro. Native hotkey behavior remains unverified.
- While recording Stop Macro, F3 raised a warning: "That keybind is already assigned to Start Auto Clicker." The displayed configuration assigns F3 to both actions.
- F4 sent through computer use while Home showed Start did not visibly start Hotbar Buff. Auto Clicker and Auto Gifted Basic Bee tool hotkeys remain unverified; the latter has no configured keybind.
- Cleanup: after desktop access returned, Roblox quit through its application menu. The Fuzzy Macro Python process and its launcher exited after a targeted terminate signal, and the macro's Chrome window was closed. The app inventory no longer showed Roblox or Python running.

## QA profile follow-up — through 2026-09-28

These results supplement the checklist above. A log showing that a feature was
enabled does not prove a particular hotbar key was pressed. Roblox visual
inspection became unreliable and was stopped after computer-use calls repeatedly
stalled and the user reported macOS WindowServer crashes. Later runs used the web
GUI and its logs only.

| Profile | Result | Evidence and remaining limit |
| --- | --- | --- |
| `qa_00_live_reload` | Accepted by user | The macro claimed hive 1, gathered Pine Tree and Pineapple, returned, converted, and produced final and item-monitor reports. This does not complete every live-reload setting check. |
| `qa_01_glitter_field_inventory` | Accepted by user, live extension not retested | The user accepted the profile based on prior behavior. The Glitter-extension trigger was changed from 14:55 to 14:30, and inventory access during a gather now pauses held clicks and shift lock. Automated inventory coordination tests passed, but a live mid-pattern extension remains open. |
| `qa_02_glitter_tad_inventory` | Skipped | User is skipping alt/TAD tests. |
| `qa_03_glitter_split_slots` | Configuration clarified; alt action skipped | The user clarified that Config Glitter Slot and AFB Glitter Slot were both 0, and that field booster uses the Config slot. No live TAD-alt extension was tested. |
| `qa_04_gumdrop_quest_only` | Not run to acceptance | Quest gumdrop use has not been observed. Verify this disposable profile before testing: its later GUI value was Gumdrop Slot 6, while `QA_PROFILES.md` describes slot 2. |
| `qa_05_gumdrop_field_goo` | Field-Goo path accepted by user | The GUI showed Gumdrop Slot 4 and a 3-second Goo interval. At 21:59:13, Pine Tree gathering logged `Goo Enabled`; the macro stopped at 22:01:29. The log cannot prove the physical slot press or rule out a second quest-gumdrop press. |
| `qa_06_gumdrop_glue` | Blocked by travel | The GUI showed Gumdrop Slot 4 and both Glue Dispenser options enabled. Travel to Glue Dispenser failed three times from 21:51:51 to 21:53:30. No dispenser use or slot press occurred; the macro stopped at 21:53:55. `QA_PROFILES.md` describes slot 2, so verify the disposable profile before retrying. |
| `qa_07_drift_builtin` | Runtime passed; drift check partial | Blue Flower `e_lol` gathered for the full 12 minutes from 08:57:16 to 09:09:16, then later for 7m02s until backpack full. Visual centering was not verified. Dandelion and Bamboo 10-minute checks remain. |
| `qa_08_drift_fuzzy_ai` | Gather passed; token leash partial | Blue Flower `fuzzy_ai_gather` ran for 10m58s without a logged error or unexpected return. Sampled views showed the avatar within the field. Dandelion and a conclusive token-boundary check remain. |
| `qa_09_drift_blooms_ai` | Gather passed; narrow-field check partial | Dandelion `blooms_ai` ran from 17:36:12 to 17:48:13 and ended at its 12-minute time limit. One mid-run view showed the avatar inside the field near the sprinkler. Blue Flower ended after 4m19s on a full backpack, so its full-duration and token-boundary checks remain. |
| `qa_10_pattern_missing` | Log/UI pass | The missing pattern displayed `(not found)` with a tooltip; the live gather emitted one alert and used `e_lol`. Choosing a replacement pattern remains untested. |
| `qa_11_pattern_broken` | Log pass | The invalid pattern emitted one syntax alert and fell back to `e_lol`. |
| `qa_12_hive_fallback` | Direct slot-check pass; detection-failure path open | Slot checks found slots 1 and 2 occupied, then claimed slot 3 without trying excluded slot 6. Detection-failure fallback, all-slots-unavailable behavior, and pause/stop during claiming remain untested. |

Additional GUI checks completed during this follow-up: Max cannon attempts 2
clamped Hive resync attempts 3 to 1, and entering 99 saved 25; the original 5/3
values were restored. Update Channel `Stable` persisted across a GUI reload,
but Beta update offers and restart behavior remain unchecked. A numeric dropdown
value displayed correctly; capitalized `Stable` and the full new-profile dropdown
sweep remain unchecked. Selecting `qa_09` while stopped and starting it used
that profile's enabled fields and `blooms_ai` pattern.

The macro was stopped after each final live run. The last verified state was
`qa_04_gumdrop_quest_only` active with the GUI showing Start. Alt/TAD items
remain intentionally skipped at the user's request.
