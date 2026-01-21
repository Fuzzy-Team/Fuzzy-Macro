# Fuzzy Macro

![Discord](https://img.shields.io/discord/1065032948119769118?label=Discord&color=7289da&logo=discord&logoColor=white&link=https://discord.gg/WdbWgFewqx)
![GitHub Repo stars](https://img.shields.io/github/stars/LaganYT/Existance-Macro?style=flat&label=Stars&color=fff240&logo=github&logocolor=white&link=https://github.com/LaganYT/Existance-Macro/stargazers)
![Repo Size](https://img.shields.io/github/repo-size/LaganYT/Existance-Macro?label=Repo%20Size&logo=github&logoColor=white)

Roblox Bee Swarm Simulator macro for macOS. Free, open source, and actively maintained.

- Docs: https://existance-macro.gitbook.io/existance-macro-docs/
- Discord: [https://discord.gg/rGRVG8Rpsb](https://discord.gg/rGRVG8Rpsb)
- Original Macro: https://github.com/existancepy/bss-macro-py
- This Macro: https://github.com/Fuzzy-Team/Fuzzy-Macro

![GUI](https://github.com/LaganYT/Existance-Macro/blob/06dd4987b68053c9bdfa842a17e51db3b7c83d30/src/gui.png)

## Features

- **Home / Control**

  - Start/stop via UI, hotkeys (F1 start, F3 stop; may require Fn), or Discord commands
  - One-click updater preserves `settings/` (profiles, patterns, paths)
  - Task list shows enabled tasks and execution order
  - Field-only mode for gathering-only operation
  - Planter timer management with visual countdowns
  - Real-time log monitoring with detailed/simple views

- **Gather**

  - Farm up to 5 fields with Natro-compatible settings
  - Patterns (shapes), size/width, invert axes, direction and turns
  - Shift-lock handling and field drift compensation (Saturator tracking)
  - Time- or backpack%-based stop conditions
  - Return-to-hive methods: Reset, Walk, Rejoin, Whirligig
  - Select start location and distance per field

- **Collect**

  - Regular dispensers (e.g., Wealth Clock, Glue, boosters, etc.)
  - Sticker Printer with egg availability detection
  - Beesmas dispensers (seasonal)
  - Memory Match (regular/mega/extreme/winter) completion
  - Blender craft/collect up to 3 items with quantity and repeat/inf modes
  - Remote enable/disable via Discord commands
  - Comprehensive collectible management system

- **Kill**

  - Regular mob runs (ladybug, rhino, werewolf, etc.) with respawn modifiers
  - Bosses: Vicious Bee (Stinger Hunt), Stump Snail, Coconut Crab
  - Night detection logic for Stinger Hunt field route
  - Optional Ant Challenge
  - Remote mob configuration via Discord
  - Vicious Bee detection with Discord notifications

- **Boost**

  - Hotbar scheduling: when and how often to trigger slots
  - Buffs: Field Boosters with spacing and gather-in-boosted-field priority
  - Sticker Stack activation (stickers or tickets) and optional Hive Skins

- **Planters**

  - Tracks placed planters and growth timing across cycles
  - Harvest by interval or when full; clear timers when needed
  - Up to 3 planters per cycle, loops cycles automatically
  - Gather in planter field and optional Glitter usage
  - Visual timer management in web interface
  - Auto-planter ranking system with optimal placement
  - Manual and automatic planter modes

- **Quests**

  - Quest-oriented gathering logic and settings (WIP; see docs)

- **Discord Bot**

  - Remote control via Discord commands (start, stop, pause, resume, skip)
  - Field management (enable/disable fields, swap fields, field-only mode)
  - Quest and collectible management
  - Mob run configuration
  - Real-time status updates and screenshots
  - Automatic stream URL pinning when streaming is enabled

- **Live Streaming**

  - Real-time screen streaming through web interface
  - Cloudflared tunnel integration for public access
  - Adaptive quality and FPS optimization
  - Mobile-friendly responsive design
  - Automatic reconnection and error handling

- **Hourly Reports & Analytics**

  - Detailed performance tracking with honey/minute statistics
  - Buff detection and uptime monitoring
  - Planter data integration
  - Historical data with trend analysis
  - Visual reports with charts and statistics
  - Automatic Discord webhook delivery

- **Web Interface**

  - Modern, responsive web-based GUI
  - Real-time log monitoring with detailed/simple views
  - Planter timer management
  - Field-only mode toggle
  - Task list visualization
  - Cross-platform accessibility

- **Notifications & Webhooks**
  - Discord webhook integration for events
  - Configurable ping notifications for:
    - Critical errors and disconnects
    - Character deaths and Vicious Bee spawns
    - Mondo Chick buffs and Ant Challenges
    - Sticker events and mob spawns
    - Conversion events and hourly reports
  - Screenshot capture and delivery
  - Stream URL sharing with auto-pinning

## Getting Started

For requirements, installation, recommended system/Roblox settings, and usage guides, see the docs:

https://existance-macro.gitbook.io/existance-macro-docs/

## Notes

- Designed for macOS.
- This project and documentation are a work in progress but actively supported.

<div class="credits-container">
  <h2>Credits</h2>
  <ul class="credits">
    <li>
      <strong>GUI Inspiration:</strong>
      <a href="https://github.com/LmeSzinc/AzurLaneAutoScript" target="_blank">AzurLaneAutoScript (ALAS)</a>
    </li>
    <li>
      <strong>Macro Inspiration:</strong>
      <a href="https://github.com/NatroTeam/NatroMacro" target="_blank">Natro Macro</a>,
      <a href="https://github.com/alaninnovates/bss-macro" target="_blank">Stumpy Macro</a>
    </li>
    <li>
      <strong>Developers:</strong> Existance, Sev, Logan
    </li>
    <li>
      <strong>Pattern Makers:</strong> Existance, NatroTeam, tvojamamkajenic, sev, dully176, chillketchup
    </li>
  </ul>
</div>

<style>
.credits-container {
  background-color: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1.5rem;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  color: var(--text-main);
  font-family: "Poppins", sans-serif;
}

.credits-container h2 {
  font-size: 1.8rem;
  margin-bottom: 1rem;
  color: var(--active-text);
}

.credits {
  list-style-type: none;
  padding: 0;
}

.credits li {
  margin-bottom: 0.8rem;
  font-size: 1rem;
}

.credits a {
  color: var(--primary);
  text-decoration: none;
}

.credits a:hover {
  color: var(--primary-hover);
  text-decoration: underline;
}
</style>
