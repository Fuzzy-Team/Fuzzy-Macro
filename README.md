<div align="center">

<!-- logo banner -->
<picture>
  <source width="200" height="200" media="(prefers-color-scheme: dark)"
          srcset="https://raw.githubusercontent.com/Fuzzy-Team/Fuzzy-Macro/refs/heads/main/.github/fuzzy.png">
  <source width="200" height="200" media="(prefers-color-scheme: light)"
          srcset="https://raw.githubusercontent.com/Fuzzy-Team/Fuzzy-Macro/refs/heads/main/.github/fuzzy-light.png">
  <img width="200" height="200" alt="Fuzzy Macro logo"
       src="https://raw.githubusercontent.com/Fuzzy-Team/Fuzzy-Macro/refs/heads/main/.github/fuzzy.png">
</picture>

<!-- shields and contents -->
![Discord](https://img.shields.io/discord/1462647649021853912?label=Discord&color=7289da&logo=discord&logoColor=white&link=https://discord.gg/rGRVG8Rpsb)
![Repo Stars](https://img.shields.io/github/stars/Fuzzy-Team/Fuzzy-Macro?style=flat&label=Stars&color=fff240&logo=github&logocolor=white&link=https://github.com/Fuzzy-Team/Fuzzy-Macro/stargazers)
![Version](https://img.shields.io/github/v/release/Fuzzy-Team/Fuzzy-Macro)
<br>
Roblox Bee Swarm Simulator macro for macOS. Free, open source, and actively maintained!<br>
<br>
[Discord](https://discord.gg/rGRVG8Rpsb) - [Existance vs. Fuzzy Macro Comparison](https://fuzzy-team.gitbook.io/fuzzy-macro/getting-started/fuzzy-macro-vs-existance-macro) - [Gitbook](https://fuzzy-team.gitbook.io/fuzzy-macro) - [Our Website](https://fuzzymacro.com)
</div>

## Getting Started

Follow our [installation guide](https://fuzzy-team.gitbook.io/fuzzy-macro) to get started, if you have any questions or need help feel free to [join our discord](https://discord.gg/rGRVG8Rpsb).

## Features

### Field Management & Gathering
- Automated field gathering with customizable patterns
- Multiple pattern support (E_lol, Cornerxe_lol, Diamond, Skillet, Kettle, etc.)
- Field drift compensation and Haste compensation
- Shift lock support
- Customizable gather duration and backpack percentage

### Planter System
- **Manual Planters**: Up to 5 cycles with 3 planters each
- **Auto Planters**: Smart planter placement based on nectar priorities
- Harvest timing based on planter type or custom intervals
- Field and nectar-specific planter ranking
- Auto gather in planter fields (Both Auto and Manual Planters Mode)

### Mob & Boss Combat
- **Regular Mobs**: Ladybugs, Rhino Beetles, Scorpions, Mantises, Spiders, Werewolf
- **Boss Mobs**:  Stump Snail, Coconut Crab, King Beetle, and Tunnel Bear
- **Stinger Hunt**: Automated Vicious Bee hunting during night
- Respawn time tracking with bonuses (Gifted Vicious, Stick Bug Amulet, Icicles Beequip)
- Automatic looting patterns
- Mob detection across multiple fields

### Collectibles & Dispensers
- Wealth Clock
- Blueberry & Strawberry Dispensers
- Coconut Dispenser
- Royal Jelly Dispenser (Free)
- Treat Dispenser
- Ant Pass Dispenser (Free)
- Glue Dispenser
- Honey Storm summoning
- Beesmas items (Stockings, Feast, Samovar, Snow Machine, Lid Art, Candles, Wreath)

### Quest System
- **Supported NPCs**: Polar Bear, Honey Bee, Bucko Bee, Riley Bee, Brown Bear, Black Bear (More to come)
- Automatic quest detection and completion
- Separate gather settings for each pollen, goo, petal, or token objective, shared across all quest givers
- Auto enables goo for goo objectives and BloomsAI for petal objectives; per-objective choices override those defaults
- Choose a field, pattern, and any gather setting per objective without changing the Gather tab; required quest fields stay fixed
- Choose quest-giver priority or share field work across quests to reduce repeat visits
- Keep the quest menu open and check completion at a chosen interval or after each pattern iteration
- Unreadable progress stays unfinished, and time or backpack limits still end a gather session
- Gumdrop support for goo gathering
- Smart field selection for quest requirements
- Quest feed bee automation

### Boost & Buff Management
- Field Dice support (Field Dice, Smooth Dice, Loaded Dice)
- Glitter automation with rebuff timing
- Mondo Buff collection with configurable wait time
- Blue/Red/Mountain Field Boosters

### Additional Features
- **Sticker Printer**: Automated sticker printing with egg selection
- **Blender**: Item crafting automation (extracts, wax, items)
- **Ant Challenge**: Automated ant challenge completion
- **Memory Match**: Support for all memory match variants
- **Cannon**: Automated cannon usage from hive (Canon access required to use Macro)

### Utility Features
- Private server support
- Automatic rejoin with configurable intervals
- Discord webhook integration
- Discord bot for remote control
- Web-based GUI for configuration
- Profile system for multiple configurations
- Task priority system with drag-and-drop ordering
- Pause/Resume functionality
- Hourly reports with statistics
- Death detection and recovery
- Screen resolution detection (See [Display Settings](https://fuzzy-team.gitbook.io/fuzzy-macro/system-settings/display-settings))

### Optional 1080p display mode

On macOS 13 or later, enable **Use 1080p virtual display** in Config → Other Settings → Display to give one Roblox client a 1920×1080 game area at normal pixel density. This can help detection on Retina screens. The setting defaults to off and applies on the next macro start.

Roblox stays windowed on a virtual monitor while a borderless preview shows the game on your physical screen. Stop keeps the virtual monitor available. Disabling the setting takes effect on the next Start and restores window placement; exiting Fuzzy also restores placement. Keyboard and mouse input still belong to the macro while it runs.

The bundled helper comes from [Fuzzy Display](https://github.com/Fuzzy-Team/Fuzzy-Display), a reduced [DeskPad](https://github.com/Stengo/DeskPad) fork. It needs Accessibility and Screen Recording permissions. The binary is ad hoc signed. Live display, input, reconnect and restoration checks passed on macOS 27.0.1 with Apple Silicon, along with a Pine Tree gather through backpack-limit detection, walking home and conversion. Physical Retina hardware, Intel runtime and clean-machine permission setup still need validation.

## Credits
### Macro Inspiration:
- <a href="https://github.com/existancepy/bss-macro-py" target="_blank">Existance Macro</a>
- Developers: [Logan](https://github.com/LaganYT)
  - Based off code written by: [Existance](https://github.com/existancepy/)
- Pattern Makers: Existance, NatroTeam, tvojamamkajenic, sev, dully176, chillketchup, Electro

## Preview
<img width="1312" height="1022" alt="image" src="https://github.com/user-attachments/assets/1cfc3c25-f51e-4ec9-9470-35636af1583e" />


## Notes

- This Macro supports macOS and Windows. Linux support is not planned.
- Fuzzy Macro is built on top of Existance Macro, meaning you can easily transitition to Fuzzy Macro. The settings and config works the same, think of Fuzzy Macro as a continuation project of Existance Macro.
