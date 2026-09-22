# Fuzzy Macro

Fuzzy Macro automates a player's recurring activities in Bee Swarm Simulator while preserving player-specific preferences and progress between runs.

## Language

**Macro Profile**:
A user-selectable collection of preferences for macro behavior, including general preferences and field-specific preferences.
_Avoid_: Profile, user profile, configuration profile

**Hive Acquisition**:
The process of finding an available hive and claiming it after joining a server. A claim succeeds when the claim prompt disappears after the claim input.
_Avoid_: Hive check, hive detection

**Gather Session**:
One continuous period of gathering in a field, from pattern setup through its final return reason. A failed pattern changes the active pattern to `e_lol` for the rest of the session.
_Avoid_: Gather loop, pattern run
