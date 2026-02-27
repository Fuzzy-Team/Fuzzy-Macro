import discord
try:
    from discord import app_commands
except ImportError:
    print("discord bot not supported")
from discord.ext import commands
from modules.screen.screenshot import screenshotRobloxWindow
import io
from modules.misc.messageBox import msgBox
from modules.misc.appManager import closeApp
from modules.controls.keyboard import keyboard
import subprocess
import sys
import os
import signal
import json
import ast
import time
from datetime import datetime, timedelta
import queue  # <-- Add this import
from typing import List, Optional, Dict, Tuple

# Import settings manager functions
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'misc'))
import settingsManager

# Hourly report dependencies
try:
    from modules.submacros.hourlyReport import HourlyReport, BuffDetector
    from modules.submacros.finalReport import FinalReport
    from modules.screen.robloxWindow import RobloxWindowBounds
except Exception:
    # Defensive: if these imports fail, the hourly report command will handle it at runtime
    HourlyReport = None
    BuffDetector = None
    FinalReport = None
    RobloxWindowBounds = None

# Global settings cache to avoid frequent file reads
_settings_cache = {}
_cache_timestamp = 0
_cache_duration = 5  # seconds

def get_cached_settings():
    """Get settings with caching to improve performance"""
    global _settings_cache, _cache_timestamp
    current_time = time.time()

    if current_time - _cache_timestamp > _cache_duration or not _settings_cache:
        _settings_cache = settingsManager.loadAllSettings()
        _cache_timestamp = current_time

    return _settings_cache

def clear_settings_cache():
    """Clear the settings cache"""
    global _settings_cache, _cache_timestamp
    _settings_cache = {}
    _cache_timestamp = 0

def update_setting(setting_key, value):
    """Update a specific setting"""
    try:
        # Convert string values to appropriate types
        if isinstance(value, str):
            if value.lower() in ['true', 'false']:
                value = value.lower() == 'true'
            elif value.isdigit():
                value = int(value)
            elif value.replace('.', '', 1).isdigit():
                value = float(value)

        settingsManager.saveGeneralSetting(setting_key, value)
        clear_settings_cache()
        return True, f"✅ Successfully updated {setting_key} to {value}"
    except Exception as e:
        return False, f"❌ Error updating setting: {str(e)}"

def update_profile_setting(setting_key, value):
    """Update a profile-specific setting"""
    try:
        # Convert string values to appropriate types
        if isinstance(value, str):
            if value.lower() in ['true', 'false']:
                value = value.lower() == 'true'
            elif value.isdigit():
                value = int(value)
            elif value.replace('.', '', 1).isdigit():
                value = float(value)

        settingsManager.saveProfileSetting(setting_key, value)
        clear_settings_cache()
        return True, f"✅ Successfully updated {setting_key} to {value}"
    except Exception as e:
        return False, f"❌ Error updating profile setting: {str(e)}"

def discordBot(token, run, status, skipTask, recentLogs=None, pin_requests=None, updateGUI=None):
    import modules.macro
    bot = commands.Bot(command_prefix="fuzz!", intents=discord.Intents.all())
    
    # Store pin requests queue
    _pin_requests = pin_requests

    @bot.event
    async def on_ready():
        print("Bot is Ready!")
        try:
            synced = await bot.tree.sync()
            print(f"Synced {len(synced)} commands")
            # Avoid printing every command by default; enable detailed
            # output by setting environment variable DISCORD_VERBOSE_SYNC=1
            if os.getenv("DISCORD_VERBOSE_SYNC", "0") == "1":
                for command in synced:
                    print(f"  - {command.name}: {command.description}")
        except Exception as e:
            print(f"Error syncing commands: {e}")
            import traceback
            traceback.print_exc()
        # Set bot presence/status
        try:
            await bot.change_presence(activity=discord.Game(name="Fuzzy Macro!"))
        except Exception as e:
            print(f"Failed to set Discord status: {e}")
        
        # Start background task to process pin requests
        if _pin_requests is not None:
            bot.loop.create_task(process_pin_requests())
    
    async def process_pin_requests():
        """Process pin requests from the queue"""
        while True:
            try:
                await discord.utils.sleep_until(datetime.now() + timedelta(seconds=1))
                
                # Check if there are any pin requests
                if _pin_requests and not _pin_requests.empty():
                    try:
                        request = _pin_requests.get_nowait()
                        channel_id = request.get('channel_id')
                        search_text = request.get('search_text', 'Stream URL')
                        
                        if channel_id:
                            await pin_message_by_search(channel_id, search_text)
                    except Exception as e:
                        print(f"Error processing pin request: {e}")
            except Exception as e:
                print(f"Error in process_pin_requests loop: {e}")
                await discord.utils.sleep_until(datetime.now() + timedelta(seconds=1))
    
    async def pin_message_by_search(channel_id, search_text):
        """Pin a message in the specified channel that contains the search text"""
        try:
            channel = bot.get_channel(int(channel_id))
            if not channel:
                channel = await bot.fetch_channel(int(channel_id))
            
            if channel:
                # First, unpin any old stream URL messages
                try:
                    pinned_messages = await channel.pins()
                    for pinned_msg in pinned_messages:
                        should_unpin = False
                        # Check embed titles/descriptions for stream indicator
                        if pinned_msg.embeds:
                            for embed in pinned_msg.embeds:
                                title = getattr(embed, 'title', '') or ''
                                desc = getattr(embed, 'description', '') or ''
                                # If title mentions Stream Started and description contains a URL or Stream URL text
                                if ("Stream Started" in title) and ("http" in desc or "Stream URL" in desc):
                                    should_unpin = True
                                    break
                                # Fallback: if description itself contains a Stream URL with http
                                if "http" in desc and ("stream" in desc.lower() or "stream url" in desc.lower()):
                                    should_unpin = True
                                    break
                        # Also check message content for URLs
                        if not should_unpin and pinned_msg.content:
                            content = pinned_msg.content or ''
                            if "http" in content and ("stream" in content.lower() or "stream url" in content.lower()):
                                should_unpin = True

                        if should_unpin:
                            try:
                                await pinned_msg.unpin()
                                print(f"Unpinned old stream message: {pinned_msg.id}")
                            except Exception as unpin_error:
                                print(f"Error unpinning message {pinned_msg.id}: {unpin_error}")
                except Exception as e:
                    print(f"Error checking/unpinning old messages: {e}")
                
                # Now search for and pin the new message
                # Get recent messages (last 10)
                messages = []
                async for message in channel.history(limit=10):
                    messages.append(message)
                
                # Search for message with the search text
                for message in messages:
                    found = False
                    # Check embeds
                    if message.embeds:
                        for embed in message.embeds:
                            title = getattr(embed, 'title', '') or ''
                            desc = getattr(embed, 'description', '') or ''
                            if search_text.lower() in title.lower() or search_text.lower() in desc.lower():
                                found = True
                                break
                    # Check message content
                    if not found and message.content and search_text.lower() in message.content.lower():
                        found = True
                    
                    if found:
                        try:
                            await message.pin()
                            print(f"Successfully pinned stream message in channel {channel_id}")
                            return
                        except Exception as pin_error:
                            print(f"Error pinning message {message.id}: {pin_error}")
                            return
                
                print(f"Could not find message with '{search_text}' in channel {channel_id}")
            else:
                print(f"Could not access channel {channel_id}")
        except Exception as e:
            print(f"Error pinning message by search: {e}")
            import traceback
            traceback.print_exc()

    def _parse_id_list(value: Optional[str]) -> List[int]:
        if not value:
            return []
        parts = [p.strip() for p in value.replace(";", ",").split(",") if p.strip()]
        ids = []
        for part in parts:
            if part.isdigit():
                ids.append(int(part))
        return ids

    def _is_authorized_interaction(interaction: discord.Interaction, requester_id: Optional[int]) -> Tuple[bool, Optional[str]]:
        if requester_id is not None and interaction.user and interaction.user.id != requester_id:
            return False, "This settings panel is tied to the user who opened it."

        owner_id = os.getenv("DISCORD_OWNER_ID")
        if owner_id and owner_id.isdigit():
            if not interaction.user or interaction.user.id != int(owner_id):
                return False, "You are not authorized to use this settings panel."
            return True, None

        role_ids = _parse_id_list(os.getenv("DISCORD_ALLOWED_ROLE_IDS"))
        if role_ids:
            if not interaction.user or not hasattr(interaction.user, "roles"):
                return False, "You are not authorized to use this settings panel."
            for role in interaction.user.roles:
                if role.id in role_ids:
                    return True, None
            return False, "You are not authorized to use this settings panel."

        return True, None

    QUEST_SETTINGS = [
        ("polar_bear_quest", "Polar Bear"),
        ("brown_bear_quest", "Brown Bear"),
        ("black_bear_quest", "Black Bear"),
        ("honey_bee_quest", "Honey Bee"),
        ("bucko_bee_quest", "Bucko Bee"),
        ("riley_bee_quest", "Riley Bee"),
        ("quest_use_gumdrops", "Use Gumdrops"),
    ]

    COLLECTIBLE_SETTINGS = [
        ("wealth_clock", "Wealth Clock"),
        ("blueberry_dispenser", "Blueberry Dispenser"),
        ("strawberry_dispenser", "Strawberry Dispenser"),
        ("coconut_dispenser", "Coconut Dispenser"),
        ("royal_jelly_dispenser", "Royal Jelly Dispenser"),
        ("ant_pass_dispenser", "Ant Pass Dispenser"),
        ("treat_dispenser", "Treat Dispenser"),
        ("glue_dispenser", "Glue Dispenser"),
        ("stockings", "Stockings"),
        ("wreath", "Wreath"),
        ("feast", "Feast"),
        ("samovar", "Samovar"),
        ("snow_machine", "Snow Machine"),
        ("lid_art", "Lid Art"),
        ("candles", "Candles"),
        ("memory_match", "Memory Match"),
        ("mega_memory_match", "Mega Memory Match"),
        ("extreme_memory_match", "Extreme Memory Match"),
        ("winter_memory_match", "Winter Memory Match"),
        ("honeystorm", "Honey Storm"),
        ("sticker_printer", "Sticker Printer"),
        ("sticker_stack", "Sticker Stack"),
        ("blue_booster", "Blue Booster"),
        ("red_booster", "Red Booster"),
        ("mountain_booster", "Mountain Booster"),
    ]

    MOB_SETTINGS = [
        ("ladybug", "Ladybug"),
        ("rhinobeetle", "Rhinobeetle"),
        ("scorpion", "Scorpion"),
        ("mantis", "Mantis"),
        ("spider", "Spider"),
        ("werewolf", "Werewolf"),
        ("coconut_crab", "Coconut Crab"),
        ("king_beetle", "King Beetle"),
        ("tunnel_bear", "Tunnel Bear"),
        ("stump_snail", "Stump Snail"),
    ]

    MACRO_MODE_OPTIONS = [
        ("normal", "Normal"),
        ("quest", "Quests"),
        ("field", "Field"),
    ]

    SETTINGS_CATEGORIES = {
        "fields": "Fields (Gather 1-5)",
        "macro_mode": "Macro Mode",
        "quests": "Quests",
        "collectibles": "Collectibles",
        "mobs": "Mobs",
        "utility": "Utility",
        "hive_slot": "Hive Slot",
    }

    UTILITY_TASK_SETTINGS = [
        ("blender", "Blender"),
        ("planters", "Planters"),
        ("ant_challenge", "Ant Challenge"),
        ("stinger_hunt", "Stinger Hunt"),
        ("mondo_buff", "Mondo Buff"),
        ("auto_field_boost", "Auto Field Boost"),
    ]

    FIELD_SECTION_OPTIONS = [
        ("basic", "Basic"),
        ("pattern", "Pattern"),
        ("until", "Gather Until"),
        ("goo", "Goo"),
        ("start", "Start"),
    ]

    RETURN_OPTIONS = [
        ("reset", "Reset"),
        ("walk", "Walk"),
        ("rejoin", "Rejoin"),
        ("whirligig", "Whirligig"),
    ]

    START_LOCATION_OPTIONS = [
        ("center", "Center"),
        ("upper right", "Upper Right"),
        ("right", "Right"),
        ("lower right", "Lower Right"),
        ("bottom", "Bottom"),
        ("lower left", "Lower Left"),
        ("left", "Left"),
        ("upper left", "Upper Left"),
        ("top", "Top"),
    ]

    def _get_task_list_order(settings: Dict) -> List[str]:
        task_list = settings.get("task_list", None)
        if isinstance(task_list, list):
            return task_list
        task_queue = settings.get("task_queue", None)
        if isinstance(task_queue, list):
            return task_queue
        return settings.get("task_priority_order", []) or []

    def _is_task_toggle_enabled(task_id: str, settings: Dict) -> bool:
        if task_id.startswith("quest_"):
            quest_key = f"{task_id.replace('quest_', '')}_quest"
            return bool(settings.get(quest_key, False))

        if task_id.startswith("collect_"):
            collect_key = task_id.replace("collect_", "")
            return bool(settings.get(collect_key, False))

        if task_id.startswith("kill_"):
            mob_key = task_id.replace("kill_", "")
            return bool(settings.get(mob_key, False))

        if task_id.startswith("gather_"):
            field_name = task_id.replace("gather_", "").replace("_", " ")
            fields = settings.get("fields", [])
            fields_enabled = settings.get("fields_enabled", [])
            for i, configured_field in enumerate(fields):
                if configured_field == field_name:
                    return i < len(fields_enabled) and bool(fields_enabled[i])
            return False

        if task_id == "blender":
            return bool(settings.get("blender_enable", False))
        if task_id == "planters":
            return bool(settings.get("planters_mode", 0))
        if task_id == "ant_challenge":
            return bool(settings.get("ant_challenge", False))
        if task_id == "stinger_hunt":
            return bool(settings.get("stinger_hunt", False))
        if task_id == "mondo_buff":
            return bool(settings.get("mondo_buff", False))
        if task_id == "auto_field_boost":
            return bool(settings.get("Auto_Field_Boost", settings.get("auto_field_boost", False)))

        return bool(settings.get(task_id, False))

    def _set_task_toggle_enabled(task_id: str, enabled: bool, settings: Dict) -> Tuple[bool, str]:
        if task_id.startswith("quest_"):
            quest_key = f"{task_id.replace('quest_', '')}_quest"
            return update_setting(quest_key, enabled)

        if task_id.startswith("collect_"):
            collect_key = task_id.replace("collect_", "")
            return update_setting(collect_key, enabled)

        if task_id.startswith("kill_"):
            mob_key = task_id.replace("kill_", "")
            return update_setting(mob_key, enabled)

        if task_id.startswith("gather_"):
            field_name = task_id.replace("gather_", "").replace("_", " ")
            fields = settings.get("fields", [])
            fields_enabled = list(settings.get("fields_enabled", []))
            for i, configured_field in enumerate(fields):
                if configured_field == field_name:
                    while i >= len(fields_enabled):
                        fields_enabled.append(False)
                    fields_enabled[i] = enabled
                    return update_setting("fields_enabled", fields_enabled)
            return False, f"Field not found for task {task_id}"

        if task_id == "blender":
            return update_setting("blender_enable", enabled)
        if task_id == "planters":
            if enabled:
                current_mode = settings.get("planters_mode", 0)
                return update_setting("planters_mode", current_mode if current_mode else 1)
            return update_setting("planters_mode", 0)
        if task_id == "ant_challenge":
            return update_setting("ant_challenge", enabled)
        if task_id == "stinger_hunt":
            return update_setting("stinger_hunt", enabled)
        if task_id == "mondo_buff":
            return update_setting("mondo_buff", enabled)
        if task_id == "auto_field_boost":
            return update_setting("Auto_Field_Boost", enabled)

        return update_setting(task_id, enabled)

    def _build_status_embed(category_key: str, settings: Dict, status_message: Optional[str] = None) -> discord.Embed:
        title = f"Settings: {SETTINGS_CATEGORIES.get(category_key, 'Settings')}"
        embed = discord.Embed(title=title, color=0x00ff00)

        def _add_enabled_disabled(enabled_items: List[str], disabled_items: List[str]):
            embed.add_field(
                name="Enabled",
                value="\n".join([f"• {item}" for item in enabled_items]) if enabled_items else "None",
                inline=False,
            )
            embed.add_field(
                name="Disabled",
                value="\n".join([f"• {item}" for item in disabled_items]) if disabled_items else "None",
                inline=False,
            )

        if category_key == "fields":
            embed.add_field(name="Gather Slots", value="Use Gather 1-5 slot panel", inline=False)
            embed.add_field(name="Controls", value="Basic, Pattern, Gather Until, Goo, Start", inline=False)

        elif category_key == "macro_mode":
            current_mode = settings.get("macro_mode", "normal")
            mode_name = dict(MACRO_MODE_OPTIONS).get(current_mode, current_mode)
            embed.add_field(name="Current", value=mode_name, inline=False)

        elif category_key == "quests":
            enabled = []
            disabled = []
            for key, label in QUEST_SETTINGS:
                if settings.get(key, False):
                    enabled.append(label)
                else:
                    disabled.append(label)
            _add_enabled_disabled(enabled, disabled)

        elif category_key == "collectibles":
            enabled = []
            disabled = []
            for key, label in COLLECTIBLE_SETTINGS:
                if settings.get(key, False):
                    enabled.append(label)
                else:
                    disabled.append(label)
            _add_enabled_disabled(enabled, disabled)

        elif category_key == "mobs":
            enabled = []
            disabled = []
            for key, label in MOB_SETTINGS:
                if settings.get(key, False):
                    enabled.append(label)
                else:
                    disabled.append(label)
            _add_enabled_disabled(enabled, disabled)

        elif category_key == "utility":
            enabled = []
            disabled = []
            for task_id, label in UTILITY_TASK_SETTINGS:
                if _is_task_toggle_enabled(task_id, settings):
                    enabled.append(label)
                else:
                    disabled.append(label)
            _add_enabled_disabled(enabled, disabled)

        elif category_key == "hive_slot":
            slot = settings.get("hive_number", "Unknown")
            embed.add_field(name="Current", value=str(slot), inline=False)

        if status_message:
            embed.set_footer(text=status_message)

        return embed

    def _build_overview_embed(settings: Dict) -> discord.Embed:
        embed = discord.Embed(title="Settings Panel", color=0x00ff00)
        field_list = settings.get("fields", [])
        fields_enabled = settings.get("fields_enabled", [])
        enabled_fields = 0
        for i in range(min(len(field_list), len(fields_enabled))):
            if fields_enabled[i]:
                enabled_fields += 1
        embed.add_field(
            name="Fields",
            value=f"Enabled: {enabled_fields}/{len(field_list)}",
            inline=False,
        )

        current_mode = settings.get("macro_mode", "normal")
        embed.add_field(
            name="Macro Mode",
            value=dict(MACRO_MODE_OPTIONS).get(current_mode, current_mode),
            inline=False,
        )

        quests_enabled = sum(1 for key, _ in QUEST_SETTINGS if settings.get(key, False))
        embed.add_field(
            name="Quests",
            value=f"Enabled: {quests_enabled}/{len(QUEST_SETTINGS)}",
            inline=False,
        )

        collectibles_enabled = sum(1 for key, _ in COLLECTIBLE_SETTINGS if settings.get(key, False))
        embed.add_field(
            name="Collectibles",
            value=f"Enabled: {collectibles_enabled}/{len(COLLECTIBLE_SETTINGS)}",
            inline=False,
        )

        mobs_enabled = sum(1 for key, _ in MOB_SETTINGS if settings.get(key, False))
        embed.add_field(
            name="Mobs",
            value=f"Enabled: {mobs_enabled}/{len(MOB_SETTINGS)}",
            inline=False,
        )

        utility_enabled = sum(1 for task_id, _ in UTILITY_TASK_SETTINGS if _is_task_toggle_enabled(task_id, settings))
        embed.add_field(
            name="Utility",
            value=f"Enabled: {utility_enabled}/{len(UTILITY_TASK_SETTINGS)}",
            inline=False,
        )

        embed.add_field(
            name="Hive Slot",
            value=str(settings.get("hive_number", "Unknown")),
            inline=False,
        )

        embed.set_footer(text="Select a category to update settings.")
        return embed

    def _get_field_slots(settings: Dict) -> Tuple[List[str], List[bool]]:
        fields = list(settings.get("fields", []))
        fields_enabled = list(settings.get("fields_enabled", []))
        while len(fields) < 5:
            fields.append("sunflower")
        while len(fields_enabled) < 5:
            fields_enabled.append(False)
        return fields, fields_enabled

    def _load_field_map() -> Dict:
        try:
            return settingsManager.loadFields()
        except Exception:
            return {}

    def _get_available_patterns(current_shape: Optional[str] = None) -> List[str]:
        try:
            patterns_dir = settingsManager.getPatternsDir()
            pattern_names = []
            for entry in os.listdir(patterns_dir):
                if entry.endswith(".py"):
                    pattern_names.append(entry[:-3])
            pattern_names = sorted(set(pattern_names))
            if current_shape and current_shape not in pattern_names:
                pattern_names.insert(0, current_shape)
            if not pattern_names:
                return ["e_lol"]
            if len(pattern_names) > 25:
                kept = pattern_names[:25]
                if current_shape and current_shape not in kept:
                    kept[-1] = current_shape
                return kept
            return pattern_names
        except Exception:
            return [current_shape] if current_shape else ["e_lol"]

    def _normalize_return_value(value: str) -> str:
        if not value:
            return "walk"
        normalized = str(value).lower().strip()
        if "reset" in normalized:
            return "reset"
        if "rejoin" in normalized:
            return "rejoin"
        if "whirligig" in normalized or "whirl" in normalized:
            return "whirligig"
        return "walk"

    def _normalize_start_location(value: str) -> str:
        if not value:
            return "center"
        normalized = str(value).lower().strip()
        valid_values = {option_value for option_value, _ in START_LOCATION_OPTIONS}
        return normalized if normalized in valid_values else "center"

    def _save_slot_field_setting(slot_index: int, setting_key: str, setting_value) -> Tuple[bool, str]:
        settings = get_cached_settings()
        fields, _ = _get_field_slots(settings)
        if slot_index < 0 or slot_index >= len(fields):
            return False, "Invalid gather slot."
        field_name = fields[slot_index]
        field_map = _load_field_map()
        field_data = dict(field_map.get(field_name, {}))
        field_data[setting_key] = setting_value
        try:
            settingsManager.saveField(field_name, field_data)
            clear_settings_cache()
            return True, f"Updated {setting_key} for Gather {slot_index + 1}."
        except Exception as e:
            return False, f"Failed to update field setting: {str(e)}"

    def _parse_bool_input(value: str, default: bool = False) -> bool:
        if value is None:
            return default
        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "yes", "y", "on", "enabled"}:
            return True
        if normalized in {"0", "false", "no", "n", "off", "disabled"}:
            return False
        return default

    def _parse_required_bool(value: str, field_label: str) -> Tuple[Optional[bool], Optional[str]]:
        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "yes", "y", "on", "enabled"}:
            return True, None
        if normalized in {"0", "false", "no", "n", "off", "disabled"}:
            return False, None
        return None, f"Invalid value for {field_label}. Use one of: true, false, yes, no, on, off, 1, 0."

    def _parse_required_int(value: str, field_label: str, min_value: Optional[int] = None, max_value: Optional[int] = None) -> Tuple[Optional[int], Optional[str]]:
        try:
            parsed = int(float(str(value).strip()))
        except Exception:
            return None, f"Invalid value for {field_label}. Enter a number."

        if min_value is not None and parsed < min_value:
            return None, f"Invalid value for {field_label}. Must be >= {min_value}."
        if max_value is not None and parsed > max_value:
            return None, f"Invalid value for {field_label}. Must be <= {max_value}."

        return parsed, None

    def _build_fields_slot_embed(slot_index: int, section_key: str, settings: Dict, status_message: Optional[str] = None) -> discord.Embed:
        fields, fields_enabled = _get_field_slots(settings)
        field_map = _load_field_map()
        field_name = fields[slot_index] if slot_index < len(fields) else "sunflower"
        field_data = dict(field_map.get(field_name, {}))
        section_label = dict(FIELD_SECTION_OPTIONS).get(section_key, section_key.title())

        embed = discord.Embed(title=f"Fields: Gather {slot_index + 1} · {section_label}", color=0x00ff00)
        embed.add_field(name="Task Enabled", value="Yes" if fields_enabled[slot_index] else "No", inline=True)
        embed.add_field(name="Field", value=field_name.title(), inline=True)

        if section_key == "basic":
            embed.add_field(name="Shift Lock", value="Yes" if field_data.get("shift_lock", False) else "No", inline=True)
            embed.add_field(name="Drift Compensation", value="Yes" if field_data.get("field_drift_compensation", False) else "No", inline=True)
        elif section_key == "pattern":
            embed.add_field(name="Shape", value=str(field_data.get("shape", "e_lol")), inline=True)
            embed.add_field(name="Size", value=str(field_data.get("size", "m")).upper(), inline=True)
            embed.add_field(name="Width", value=str(field_data.get("width", 3)), inline=True)
            embed.add_field(name="Invert L/R", value="Yes" if field_data.get("invert_lr", False) else "No", inline=True)
            embed.add_field(name="Invert F/B", value="Yes" if field_data.get("invert_fb", False) else "No", inline=True)
            embed.add_field(name="Turn", value=str(field_data.get("turn", "none")).title(), inline=True)
            embed.add_field(name="Turn Times", value=str(field_data.get("turn_times", 1)), inline=True)
        elif section_key == "until":
            embed.add_field(name="Mins", value=str(field_data.get("mins", 8)), inline=True)
            embed.add_field(name="Backpack %", value=str(field_data.get("backpack", 95)), inline=True)
            embed.add_field(name="Return", value=_normalize_return_value(str(field_data.get("return", "walk"))).title(), inline=True)
            embed.add_field(name="Whirligig Fallback", value="Yes" if field_data.get("use_whirlwig_fallback", False) else "No", inline=True)
        elif section_key == "goo":
            embed.add_field(name="Use Goo", value="Yes" if field_data.get("goo", False) else "No", inline=True)
            embed.add_field(name="Goo Interval", value=f"{field_data.get('goo_interval', 3)}s", inline=True)
        elif section_key == "start":
            start_location = _normalize_start_location(str(field_data.get("start_location", "center")))
            embed.add_field(name="Start Location", value=start_location.title(), inline=True)
            embed.add_field(name="Distance", value=str(field_data.get("distance", 1)), inline=True)

        embed.set_footer(text=status_message or "Gather tabs: 1-5. Choose a section to control more settings.")
        return embed

    async def _update_fields_message(
        interaction: discord.Interaction,
        slot_index: int,
        section_key: str,
        status_message: Optional[str] = None,
        dropdown_key: Optional[str] = None,
        source_channel_id: Optional[int] = None,
        source_message_id: Optional[int] = None,
    ):
        settings = get_cached_settings()
        view = FieldsPanelView(
            slot_index=slot_index,
            section_key=section_key,
            requester_id=interaction.user.id,
            status_message=status_message,
            dropdown_key=dropdown_key,
        )
        embed = _build_fields_slot_embed(slot_index, section_key, settings, status_message=status_message)

        if source_channel_id and source_message_id:
            try:
                channel = interaction.client.get_channel(source_channel_id)
                if channel is None:
                    channel = await interaction.client.fetch_channel(source_channel_id)
                message = await channel.fetch_message(source_message_id)
                await message.edit(embed=embed, view=view)
                ack_text = status_message or "Updated fields settings."
                if interaction.response.is_done():
                    await interaction.followup.send(ack_text, ephemeral=True)
                else:
                    await interaction.response.send_message(ack_text, ephemeral=True)
                return
            except Exception:
                pass

        try:
            await interaction.response.edit_message(embed=embed, view=view)
            return
        except Exception:
            pass

        try:
            if getattr(interaction, "message", None):
                await interaction.message.edit(embed=embed, view=view)
                if not interaction.response.is_done() and status_message:
                    await interaction.response.send_message(status_message, ephemeral=True)
                return
        except Exception:
            pass

        if interaction.response.is_done():
            await interaction.followup.send(status_message or "Updated fields settings.", ephemeral=True)
        else:
            await interaction.response.send_message(status_message or "Updated fields settings.", ephemeral=True)

    async def _update_category_message(interaction: discord.Interaction, category_key: str, status_message: Optional[str] = None):
        if category_key == "fields":
            await _update_fields_message(interaction, slot_index=0, section_key="basic", status_message=status_message)
            return
        settings = get_cached_settings()
        view = SettingsCategoryView(category_key, requester_id=interaction.user.id, status_message=status_message)
        embed = _build_status_embed(category_key, settings, status_message=status_message)
        await interaction.response.edit_message(embed=embed, view=view)

    def _format_task_name(task_id: str) -> str:
        if task_id.startswith("quest_"):
            return f"Quest: {task_id.replace('quest_', '').replace('_', ' ').title()}"
        if task_id.startswith("collect_"):
            return f"Collect: {task_id.replace('collect_', '').replace('_', ' ').title()}"
        if task_id.startswith("kill_"):
            return f"Kill: {task_id.replace('kill_', '').replace('_', ' ').title()}"
        if task_id.startswith("gather_"):
            return f"Gather: {task_id.replace('gather_', '').replace('_', ' ').title()}"
        if task_id.startswith("feed_bee_"):
            return f"Feed Bee: {task_id.replace('feed_bee_', '').replace('_', ' ').title()}"

        special_names = {
            "blender": "Blender",
            "planters": "Planters",
            "ant_challenge": "Ant Challenge",
            "stinger_hunt": "Stinger Hunt",
            "mondo_buff": "Mondo Buff",
            "auto_field_boost": "Auto Field Boost",
        }
        return special_names.get(task_id, task_id.replace("_", " ").title())

    def _is_task_enabled(task_id: str, settings: Dict) -> bool:
        macro_mode = settings.get("macro_mode", "normal")

        if macro_mode == "field" and not task_id.startswith("gather_"):
            return False
        if macro_mode == "quest" and not task_id.startswith("quest_"):
            return False

        if task_id.startswith("quest_"):
            quest_key = f"{task_id.replace('quest_', '')}_quest"
            return bool(settings.get(quest_key, False))

        if task_id.startswith("collect_"):
            collect_key = task_id.replace("collect_", "")
            return bool(settings.get(collect_key, False))

        if task_id.startswith("kill_"):
            mob_key = task_id.replace("kill_", "")
            return bool(settings.get(mob_key, False))

        if task_id.startswith("gather_"):
            field_name = task_id.replace("gather_", "").replace("_", " ")
            fields = settings.get("fields", [])
            fields_enabled = settings.get("fields_enabled", [])
            for i, configured_field in enumerate(fields):
                if configured_field == field_name:
                    return i < len(fields_enabled) and bool(fields_enabled[i])
            return False

        if task_id == "blender":
            return bool(settings.get("blender_enable", False))
        if task_id == "planters":
            return bool(settings.get("planters_mode", 0))
        if task_id == "ant_challenge":
            return bool(settings.get("ant_challenge", False))
        if task_id == "stinger_hunt":
            return bool(settings.get("stinger_hunt", False))
        if task_id == "mondo_buff":
            return bool(settings.get("mondo_buff", False))
        if task_id == "auto_field_boost":
            return bool(settings.get("Auto_Field_Boost", settings.get("auto_field_boost", False)))

        return bool(settings.get(task_id, False))

    def _get_enabled_task_order(settings: Dict) -> List[str]:
        task_list_order = _get_task_list_order(settings)
        enabled_tasks = [task_id for task_id in task_list_order if _is_task_enabled(task_id, settings)]

        macro_mode = settings.get("macro_mode", "normal")

        if macro_mode == "field" and not enabled_tasks:
            fields = settings.get("fields", [])
            fields_enabled = settings.get("fields_enabled", [])
            for i, field_name in enumerate(fields):
                if i < len(fields_enabled) and fields_enabled[i]:
                    enabled_tasks.append(f"gather_{field_name.replace(' ', '_')}")

        if macro_mode == "quest" and not enabled_tasks:
            for quest_key, _ in QUEST_SETTINGS:
                if quest_key.endswith("_quest") and settings.get(quest_key, False):
                    quest_name = quest_key.replace("_quest", "")
                    enabled_tasks.append(f"quest_{quest_name}")

        return enabled_tasks

    def _normalize_current_task_to_priority_task(current_task: str, settings: Dict, queue_order: List[str]) -> Optional[str]:
        if not current_task:
            return None

        if current_task in queue_order:
            return current_task

        if current_task.startswith("planter_") and "planters" in queue_order:
            return "planters"

        if current_task.startswith("travelling_"):
            travelling_target = current_task.replace("travelling_", "")
            gather_candidate = f"gather_{travelling_target}"
            if gather_candidate in queue_order:
                return gather_candidate

        kill_candidate = f"kill_{current_task}"
        if kill_candidate in queue_order:
            return kill_candidate

        collect_candidate = f"collect_{current_task}"
        if collect_candidate in queue_order:
            return collect_candidate

        return None

    class SettingsBaseView(discord.ui.View):
        def __init__(self, requester_id: Optional[int], timeout: int = 300):
            super().__init__(timeout=timeout)
            self.requester_id = requester_id

        async def interaction_check(self, interaction: discord.Interaction) -> bool:
            allowed, message = _is_authorized_interaction(interaction, self.requester_id)
            if not allowed:
                if interaction.response.is_done():
                    await interaction.followup.send(message, ephemeral=True)
                else:
                    await interaction.response.send_message(message, ephemeral=True)
                return False
            return True

    class CategorySelect(discord.ui.Select):
        def __init__(self):
            options = [
                discord.SelectOption(label=label, value=key)
                for key, label in SETTINGS_CATEGORIES.items()
            ]
            super().__init__(placeholder="Choose a settings category", min_values=1, max_values=1, options=options)

        async def callback(self, interaction: discord.Interaction):
            category_key = self.values[0]
            if category_key == "fields":
                await _update_fields_message(interaction, slot_index=0, section_key="basic")
                return
            settings = get_cached_settings()
            view = SettingsCategoryView(category_key, requester_id=interaction.user.id)
            embed = _build_status_embed(category_key, settings)
            await interaction.response.edit_message(embed=embed, view=view)

    class BackButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Back", style=discord.ButtonStyle.secondary)

        async def callback(self, interaction: discord.Interaction):
            settings = get_cached_settings()
            view = SettingsHomeView(requester_id=interaction.user.id)
            embed = _build_overview_embed(settings)
            await interaction.response.edit_message(embed=embed, view=view)

    class CategoryBackButton(discord.ui.Button):
        def __init__(self, category_key: str):
            self.category_key = category_key
            super().__init__(label="Back to Category", style=discord.ButtonStyle.secondary)

        async def callback(self, interaction: discord.Interaction):
            settings = get_cached_settings()
            view = SettingsCategoryView(self.category_key, requester_id=interaction.user.id)
            embed = _build_status_embed(self.category_key, settings)
            await interaction.response.edit_message(embed=embed, view=view)

    class RefreshButton(discord.ui.Button):
        def __init__(self, category_key: str):
            self.category_key = category_key
            super().__init__(label="Refresh", style=discord.ButtonStyle.secondary)

        async def callback(self, interaction: discord.Interaction):
            await _update_category_message(interaction, self.category_key, status_message="Refreshed settings.")

    class OpenFieldsPanelButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Open Gather 1-5 Panel", style=discord.ButtonStyle.primary)

        async def callback(self, interaction: discord.Interaction):
            await _update_fields_message(interaction, slot_index=0, section_key="basic")

    class FieldsSlotSelect(discord.ui.Select):
        def __init__(self, current_slot: int):
            options = []
            for slot_index in range(5):
                options.append(
                    discord.SelectOption(
                        label=f"Gather {slot_index + 1}",
                        value=str(slot_index),
                        default=(slot_index == current_slot),
                    )
                )
            super().__init__(placeholder="Choose gather slot", min_values=1, max_values=1, options=options)

        async def callback(self, interaction: discord.Interaction):
            slot_index = int(self.values[0])
            section_key = self.view.section_key if hasattr(self.view, "section_key") else "basic"
            dropdown_key = self.view.dropdown_key if hasattr(self.view, "dropdown_key") else None
            await _update_fields_message(interaction, slot_index=slot_index, section_key=section_key, dropdown_key=dropdown_key)

    class FieldsSectionSelect(discord.ui.Select):
        def __init__(self, current_section: str):
            options = []
            for section_key, section_label in FIELD_SECTION_OPTIONS:
                options.append(
                    discord.SelectOption(
                        label=section_label,
                        value=section_key,
                        default=(section_key == current_section),
                    )
                )
            super().__init__(placeholder="Choose field section", min_values=1, max_values=1, options=options)

        async def callback(self, interaction: discord.Interaction):
            section_key = self.values[0]
            slot_index = self.view.slot_index if hasattr(self.view, "slot_index") else 0
            dropdown_key = "shape" if section_key == "pattern" else None
            await _update_fields_message(interaction, slot_index=slot_index, section_key=section_key, dropdown_key=dropdown_key)

    class FieldNameSelect(discord.ui.Select):
        def __init__(self, current_field: str):
            field_map = _load_field_map()
            field_names = sorted(field_map.keys()) or [current_field]
            if current_field not in field_names:
                field_names.insert(0, current_field)
            options = [
                discord.SelectOption(label=name.title(), value=name, default=(name == current_field))
                for name in field_names[:25]
            ]
            super().__init__(placeholder="Set field", min_values=1, max_values=1, options=options)

        async def callback(self, interaction: discord.Interaction):
            slot_index = self.view.slot_index
            settings = get_cached_settings()
            fields, _ = _get_field_slots(settings)
            fields[slot_index] = self.values[0]
            success, message = update_setting("fields", fields)
            status_message = message if success else "Failed to update slot field."
            await _update_fields_message(interaction, slot_index=slot_index, section_key=self.view.section_key, status_message=status_message, dropdown_key=self.view.dropdown_key if hasattr(self.view, "dropdown_key") else None)

    class FieldBasicToggleSelect(discord.ui.Select):
        def __init__(self, task_enabled: bool, shift_lock: bool, drift: bool):
            options = [
                discord.SelectOption(label="Enable Task", value="task_enabled", default=task_enabled),
                discord.SelectOption(label="Shift Lock", value="shift_lock", default=shift_lock),
                discord.SelectOption(label="Drift Compensation", value="field_drift_compensation", default=drift),
            ]
            super().__init__(placeholder="Basic toggles", min_values=0, max_values=3, options=options)

        async def callback(self, interaction: discord.Interaction):
            slot_index = self.view.slot_index
            selected = set(self.values)
            settings = get_cached_settings()
            fields, fields_enabled = _get_field_slots(settings)

            fields_enabled[slot_index] = "task_enabled" in selected
            success_enabled, _ = update_setting("fields_enabled", fields_enabled)

            failures = [] if success_enabled else ["task_enabled"]
            for key in ("shift_lock", "field_drift_compensation"):
                success, _ = _save_slot_field_setting(slot_index, key, key in selected)
                if not success:
                    failures.append(key)

            status_message = "Updated basic settings." if not failures else "Some basic settings failed to update."
            await _update_fields_message(interaction, slot_index=slot_index, section_key=self.view.section_key, status_message=status_message)

    class FieldShapeSelect(discord.ui.Select):
        def __init__(self, current_shape: str):
            patterns = _get_available_patterns(current_shape=current_shape)
            options = [discord.SelectOption(label=p, value=p, default=(p == current_shape)) for p in patterns]
            super().__init__(placeholder="Pattern shape", min_values=1, max_values=1, options=options)

        async def callback(self, interaction: discord.Interaction):
            success, message = _save_slot_field_setting(self.view.slot_index, "shape", self.values[0])
            await _update_fields_message(interaction, slot_index=self.view.slot_index, section_key=self.view.section_key, status_message=(message if success else "Failed to update shape."))

    class FieldSizeSelect(discord.ui.Select):
        def __init__(self, current_size: str):
            options = [
                discord.SelectOption(label=size.upper(), value=size.lower(), default=(size.lower() == str(current_size).lower()))
                for size in ["xs", "s", "m", "l", "xl"]
            ]
            super().__init__(placeholder="Pattern size", min_values=1, max_values=1, options=options)

        async def callback(self, interaction: discord.Interaction):
            success, message = _save_slot_field_setting(self.view.slot_index, "size", self.values[0])
            await _update_fields_message(interaction, slot_index=self.view.slot_index, section_key=self.view.section_key, status_message=(message if success else "Failed to update size."))

    class FieldWidthSelect(discord.ui.Select):
        def __init__(self, current_width):
            width_str = str(current_width)
            options = [
                discord.SelectOption(label=str(width), value=str(width), default=(str(width) == width_str))
                for width in range(1, 9)
            ]
            super().__init__(placeholder="Pattern width", min_values=1, max_values=1, options=options)

        async def callback(self, interaction: discord.Interaction):
            success, message = _save_slot_field_setting(self.view.slot_index, "width", int(self.values[0]))
            await _update_fields_message(interaction, slot_index=self.view.slot_index, section_key=self.view.section_key, status_message=(message if success else "Failed to update width."))

    class FieldPatternToggleSelect(discord.ui.Select):
        def __init__(self, invert_lr: bool, invert_fb: bool):
            options = [
                discord.SelectOption(label="Invert Left/Right", value="invert_lr", default=invert_lr),
                discord.SelectOption(label="Invert Forward/Back", value="invert_fb", default=invert_fb),
            ]
            super().__init__(placeholder="Pattern invert toggles", min_values=0, max_values=2, options=options)

        async def callback(self, interaction: discord.Interaction):
            selected = set(self.values)
            failures = []
            for key in ("invert_lr", "invert_fb"):
                success, _ = _save_slot_field_setting(self.view.slot_index, key, key in selected)
                if not success:
                    failures.append(key)
            status_message = "Updated invert settings." if not failures else "Some invert settings failed to update."
            await _update_fields_message(interaction, slot_index=self.view.slot_index, section_key=self.view.section_key, status_message=status_message)

    class FieldTurnDirectionSelect(discord.ui.Select):
        def __init__(self, current_turn: str):
            turn_value = str(current_turn).lower()
            options = [
                discord.SelectOption(label="None", value="none", default=(turn_value == "none")),
                discord.SelectOption(label="Left", value="left", default=(turn_value == "left")),
                discord.SelectOption(label="Right", value="right", default=(turn_value == "right")),
            ]
            super().__init__(placeholder="Turn direction", min_values=1, max_values=1, options=options)

        async def callback(self, interaction: discord.Interaction):
            success, message = _save_slot_field_setting(self.view.slot_index, "turn", self.values[0])
            await _update_fields_message(interaction, slot_index=self.view.slot_index, section_key=self.view.section_key, status_message=(message if success else "Failed to update turn direction."))

    class FieldTurnTimesSelect(discord.ui.Select):
        def __init__(self, current_turn_times):
            current = str(current_turn_times)
            options = [
                discord.SelectOption(label=str(count), value=str(count), default=(str(count) == current))
                for count in [1, 2, 3, 4]
            ]
            super().__init__(placeholder="Turn times", min_values=1, max_values=1, options=options)

        async def callback(self, interaction: discord.Interaction):
            success, message = _save_slot_field_setting(self.view.slot_index, "turn_times", int(self.values[0]))
            await _update_fields_message(interaction, slot_index=self.view.slot_index, section_key=self.view.section_key, status_message=(message if success else "Failed to update turn count."))

    class FieldMinsSelect(discord.ui.Select):
        def __init__(self, current_mins):
            values = [1, 2, 3, 5, 8, 10, 12, 15, 20, 30]
            current = str(int(float(current_mins))) if str(current_mins).replace('.', '', 1).isdigit() else str(current_mins)
            options = [
                discord.SelectOption(label=str(v), value=str(v), default=(str(v) == current))
                for v in values
            ]
            super().__init__(placeholder="Gather mins", min_values=1, max_values=1, options=options)

        async def callback(self, interaction: discord.Interaction):
            success, message = _save_slot_field_setting(self.view.slot_index, "mins", int(self.values[0]))
            await _update_fields_message(interaction, slot_index=self.view.slot_index, section_key=self.view.section_key, status_message=(message if success else "Failed to update mins."))

    class FieldBackpackSelect(discord.ui.Select):
        def __init__(self, current_backpack):
            values = [70, 80, 85, 90, 95, 98, 100]
            current = str(int(float(current_backpack))) if str(current_backpack).replace('.', '', 1).isdigit() else str(current_backpack)
            options = [
                discord.SelectOption(label=f"{v}%", value=str(v), default=(str(v) == current))
                for v in values
            ]
            super().__init__(placeholder="Backpack percent", min_values=1, max_values=1, options=options)

        async def callback(self, interaction: discord.Interaction):
            success, message = _save_slot_field_setting(self.view.slot_index, "backpack", int(self.values[0]))
            await _update_fields_message(interaction, slot_index=self.view.slot_index, section_key=self.view.section_key, status_message=(message if success else "Failed to update backpack percent."))

    class FieldReturnSelect(discord.ui.Select):
        def __init__(self, current_return: str):
            normalized = _normalize_return_value(current_return)
            options = [
                discord.SelectOption(label=label, value=value, default=(value == normalized))
                for value, label in RETURN_OPTIONS
            ]
            super().__init__(placeholder="Return method", min_values=1, max_values=1, options=options)

        async def callback(self, interaction: discord.Interaction):
            success, message = _save_slot_field_setting(self.view.slot_index, "return", self.values[0])
            await _update_fields_message(interaction, slot_index=self.view.slot_index, section_key=self.view.section_key, status_message=(message if success else "Failed to update return method."), dropdown_key=self.view.dropdown_key if hasattr(self.view, "dropdown_key") else None)

    class FieldWhirligigFallbackSelect(discord.ui.Select):
        def __init__(self, enabled: bool):
            options = [discord.SelectOption(label="Use Whirligig Fallback", value="enabled", default=enabled)]
            super().__init__(placeholder="Whirligig fallback", min_values=0, max_values=1, options=options)

        async def callback(self, interaction: discord.Interaction):
            success, message = _save_slot_field_setting(self.view.slot_index, "use_whirlwig_fallback", "enabled" in self.values)
            await _update_fields_message(interaction, slot_index=self.view.slot_index, section_key=self.view.section_key, status_message=(message if success else "Failed to update whirligig fallback."))

    class FieldGooToggleSelect(discord.ui.Select):
        def __init__(self, enabled: bool):
            options = [discord.SelectOption(label="Use Goo", value="goo", default=enabled)]
            super().__init__(placeholder="Goo toggle", min_values=0, max_values=1, options=options)

        async def callback(self, interaction: discord.Interaction):
            success, message = _save_slot_field_setting(self.view.slot_index, "goo", "goo" in self.values)
            await _update_fields_message(interaction, slot_index=self.view.slot_index, section_key=self.view.section_key, status_message=(message if success else "Failed to update goo toggle."))

    class FieldGooIntervalSelect(discord.ui.Select):
        def __init__(self, current_interval):
            values = [3, 5, 8, 10, 12, 15, 20, 30, 45, 60]
            current = str(int(float(current_interval))) if str(current_interval).replace('.', '', 1).isdigit() else str(current_interval)
            options = [
                discord.SelectOption(label=f"{v}s", value=str(v), default=(str(v) == current))
                for v in values
            ]
            super().__init__(placeholder="Goo interval", min_values=1, max_values=1, options=options)

        async def callback(self, interaction: discord.Interaction):
            success, message = _save_slot_field_setting(self.view.slot_index, "goo_interval", int(self.values[0]))
            await _update_fields_message(interaction, slot_index=self.view.slot_index, section_key=self.view.section_key, status_message=(message if success else "Failed to update goo interval."))

    class FieldStartLocationSelect(discord.ui.Select):
        def __init__(self, current_location: str):
            normalized = _normalize_start_location(current_location)
            options = [
                discord.SelectOption(label=label, value=value, default=(value == normalized))
                for value, label in START_LOCATION_OPTIONS
            ]
            super().__init__(placeholder="Start location", min_values=1, max_values=1, options=options)

        async def callback(self, interaction: discord.Interaction):
            success, message = _save_slot_field_setting(self.view.slot_index, "start_location", self.values[0])
            await _update_fields_message(interaction, slot_index=self.view.slot_index, section_key=self.view.section_key, status_message=(message if success else "Failed to update start location."), dropdown_key=self.view.dropdown_key if hasattr(self.view, "dropdown_key") else None)

    class FieldDistanceSelect(discord.ui.Select):
        def __init__(self, current_distance):
            current = str(int(float(current_distance))) if str(current_distance).replace('.', '', 1).isdigit() else str(current_distance)
            options = [
                discord.SelectOption(label=str(v), value=str(v), default=(str(v) == current))
                for v in range(1, 11)
            ]
            super().__init__(placeholder="Start distance", min_values=1, max_values=1, options=options)

        async def callback(self, interaction: discord.Interaction):
            success, message = _save_slot_field_setting(self.view.slot_index, "distance", int(self.values[0]))
            await _update_fields_message(interaction, slot_index=self.view.slot_index, section_key=self.view.section_key, status_message=(message if success else "Failed to update start distance."), dropdown_key=self.view.dropdown_key if hasattr(self.view, "dropdown_key") else None)

    class RefreshFieldsButton(discord.ui.Button):
        def __init__(self, slot_index: int, section_key: str):
            self.slot_index = slot_index
            self.section_key = section_key
            super().__init__(label="Refresh", style=discord.ButtonStyle.secondary)

        async def callback(self, interaction: discord.Interaction):
            await _update_fields_message(interaction, self.slot_index, self.section_key, status_message="Refreshed fields settings.")

    class BasicFieldModal(discord.ui.Modal, title="Edit Basic Field Settings"):
        def __init__(self, slot_index: int, section_key: str, field_name: str, task_enabled: bool, shift_lock: bool, drift: bool, source_channel_id: Optional[int] = None, source_message_id: Optional[int] = None):
            super().__init__()
            self.slot_index = slot_index
            self.section_key = section_key
            self.source_channel_id = source_channel_id
            self.source_message_id = source_message_id
            self.field_name_input = discord.ui.TextInput(label="Field Name", default=field_name, required=True, max_length=32)
            self.task_enabled_input = discord.ui.TextInput(label="Enable Task (true/false)", default=str(task_enabled), required=True, max_length=8)
            self.shift_lock_input = discord.ui.TextInput(label="Shift Lock (true/false)", default=str(shift_lock), required=True, max_length=8)
            self.drift_input = discord.ui.TextInput(label="Drift Compensation (true/false)", default=str(drift), required=True, max_length=8)
            self.add_item(self.field_name_input)
            self.add_item(self.task_enabled_input)
            self.add_item(self.shift_lock_input)
            self.add_item(self.drift_input)

        async def on_submit(self, interaction: discord.Interaction):
            settings = get_cached_settings()
            fields, fields_enabled = _get_field_slots(settings)
            field_map = _load_field_map()
            requested_field = str(self.field_name_input.value).strip().lower()

            if requested_field not in field_map:
                await interaction.response.send_message(f"Unknown field '{requested_field}'.", ephemeral=True)
                return

            task_enabled_value, task_enabled_error = _parse_required_bool(self.task_enabled_input.value, "Enable Task")
            shift_lock_value, shift_lock_error = _parse_required_bool(self.shift_lock_input.value, "Shift Lock")
            drift_value, drift_error = _parse_required_bool(self.drift_input.value, "Drift Compensation")

            validation_errors = [e for e in [task_enabled_error, shift_lock_error, drift_error] if e]
            if validation_errors:
                await interaction.response.send_message("\n".join(validation_errors), ephemeral=True)
                return

            fields[self.slot_index] = requested_field
            fields_enabled[self.slot_index] = bool(task_enabled_value)
            success_fields, _ = update_setting("fields", fields)
            success_enabled, _ = update_setting("fields_enabled", fields_enabled)

            success_shift, _ = _save_slot_field_setting(self.slot_index, "shift_lock", bool(shift_lock_value))
            success_drift, _ = _save_slot_field_setting(self.slot_index, "field_drift_compensation", bool(drift_value))

            failures = []
            if not success_fields:
                failures.append("fields")
            if not success_enabled:
                failures.append("fields_enabled")
            if not success_shift:
                failures.append("shift_lock")
            if not success_drift:
                failures.append("field_drift_compensation")

            status_message = "Updated basic settings." if not failures else "Some basic settings failed to update."
            await _update_fields_message(
                interaction,
                slot_index=self.slot_index,
                section_key=self.section_key,
                status_message=status_message,
                source_channel_id=self.source_channel_id,
                source_message_id=self.source_message_id,
            )

    class PatternFlagsModal(discord.ui.Modal, title="Edit Pattern Flags"):
        def __init__(self, slot_index: int, section_key: str, field_data: Dict, source_channel_id: Optional[int] = None, source_message_id: Optional[int] = None):
            super().__init__()
            self.slot_index = slot_index
            self.section_key = section_key
            self.source_channel_id = source_channel_id
            self.source_message_id = source_message_id
            self.invert_lr_input = discord.ui.TextInput(label="Invert L/R (true/false)", default=str(bool(field_data.get("invert_lr", False))), required=True, max_length=8)
            self.invert_fb_input = discord.ui.TextInput(label="Invert F/B (true/false)", default=str(bool(field_data.get("invert_fb", False))), required=True, max_length=8)
            self.add_item(self.invert_lr_input)
            self.add_item(self.invert_fb_input)

        async def on_submit(self, interaction: discord.Interaction):
            invert_lr_value, invert_lr_error = _parse_required_bool(self.invert_lr_input.value, "Invert L/R")
            invert_fb_value, invert_fb_error = _parse_required_bool(self.invert_fb_input.value, "Invert F/B")
            validation_errors = [e for e in [invert_lr_error, invert_fb_error] if e]
            if validation_errors:
                await interaction.response.send_message("\n".join(validation_errors), ephemeral=True)
                return

            failures = []
            success, _ = _save_slot_field_setting(self.slot_index, "invert_lr", bool(invert_lr_value))
            if not success:
                failures.append("invert_lr")
            success, _ = _save_slot_field_setting(self.slot_index, "invert_fb", bool(invert_fb_value))
            if not success:
                failures.append("invert_fb")

            status_message = "Updated pattern flags." if not failures else "Some pattern flags failed to update."
            await _update_fields_message(
                interaction,
                slot_index=self.slot_index,
                section_key=self.section_key,
                status_message=status_message,
                dropdown_key="shape",
                source_channel_id=self.source_channel_id,
                source_message_id=self.source_message_id,
            )

    class UntilFieldModal(discord.ui.Modal, title="Edit Gather Until Settings"):
        def __init__(self, slot_index: int, section_key: str, field_data: Dict, source_channel_id: Optional[int] = None, source_message_id: Optional[int] = None):
            super().__init__()
            self.slot_index = slot_index
            self.section_key = section_key
            self.source_channel_id = source_channel_id
            self.source_message_id = source_message_id
            self.mins_input = discord.ui.TextInput(label="Mins", default=str(field_data.get("mins", 8)), required=True, max_length=4)
            self.backpack_input = discord.ui.TextInput(label="Backpack %", default=str(field_data.get("backpack", 95)), required=True, max_length=4)
            self.whirl_fallback_input = discord.ui.TextInput(label="Whirligig Fallback (true/false)", default=str(bool(field_data.get("use_whirlwig_fallback", False))), required=True, max_length=8)
            self.add_item(self.mins_input)
            self.add_item(self.backpack_input)
            self.add_item(self.whirl_fallback_input)

        async def on_submit(self, interaction: discord.Interaction):
            mins_value, mins_error = _parse_required_int(self.mins_input.value, "Mins", min_value=1)
            backpack_value, backpack_error = _parse_required_int(self.backpack_input.value, "Backpack %", min_value=1, max_value=100)
            whirl_fallback_value, whirl_fallback_error = _parse_required_bool(self.whirl_fallback_input.value, "Whirligig Fallback")
            validation_errors = [e for e in [mins_error, backpack_error, whirl_fallback_error] if e]
            if validation_errors:
                await interaction.response.send_message("\n".join(validation_errors), ephemeral=True)
                return

            failures = []
            success, _ = _save_slot_field_setting(self.slot_index, "mins", int(mins_value))
            if not success:
                failures.append("mins")

            success, _ = _save_slot_field_setting(self.slot_index, "backpack", int(backpack_value))
            if not success:
                failures.append("backpack")

            success, _ = _save_slot_field_setting(self.slot_index, "use_whirlwig_fallback", bool(whirl_fallback_value))
            if not success:
                failures.append("use_whirlwig_fallback")

            status_message = "Updated gather-until settings." if not failures else "Some gather-until settings failed to update."
            await _update_fields_message(
                interaction,
                slot_index=self.slot_index,
                section_key=self.section_key,
                status_message=status_message,
                source_channel_id=self.source_channel_id,
                source_message_id=self.source_message_id,
            )

    class GooFieldModal(discord.ui.Modal, title="Edit Goo Settings"):
        def __init__(self, slot_index: int, section_key: str, field_data: Dict, source_channel_id: Optional[int] = None, source_message_id: Optional[int] = None):
            super().__init__()
            self.slot_index = slot_index
            self.section_key = section_key
            self.source_channel_id = source_channel_id
            self.source_message_id = source_message_id
            self.goo_input = discord.ui.TextInput(label="Use Goo (true/false)", default=str(bool(field_data.get("goo", False))), required=True, max_length=8)
            self.interval_input = discord.ui.TextInput(label="Goo Interval Seconds", default=str(field_data.get("goo_interval", 3)), required=True, max_length=4)
            self.add_item(self.goo_input)
            self.add_item(self.interval_input)

        async def on_submit(self, interaction: discord.Interaction):
            goo_value, goo_error = _parse_required_bool(self.goo_input.value, "Use Goo")
            interval_value, interval_error = _parse_required_int(self.interval_input.value, "Goo Interval Seconds", min_value=1)

            validation_errors = [e for e in [goo_error, interval_error] if e]
            if validation_errors:
                await interaction.response.send_message("\n".join(validation_errors), ephemeral=True)
                return

            failures = []
            success, _ = _save_slot_field_setting(self.slot_index, "goo", bool(goo_value))
            if not success:
                failures.append("goo")
            success, _ = _save_slot_field_setting(self.slot_index, "goo_interval", int(interval_value))
            if not success:
                failures.append("goo_interval")
            status_message = "Updated goo settings." if not failures else "Some goo settings failed to update."
            await _update_fields_message(
                interaction,
                slot_index=self.slot_index,
                section_key=self.section_key,
                status_message=status_message,
                source_channel_id=self.source_channel_id,
                source_message_id=self.source_message_id,
            )

    class StartFieldModal(discord.ui.Modal, title="Edit Start Settings"):
        def __init__(self, slot_index: int, section_key: str, field_data: Dict):
            super().__init__()
            self.slot_index = slot_index
            self.section_key = section_key
            self.note_input = discord.ui.TextInput(label="No form fields needed", default="Start settings use dropdowns below.", required=False, max_length=64)
            self.add_item(self.note_input)

        async def on_submit(self, interaction: discord.Interaction):
            status_message = "Start settings use dropdowns in the panel."
            await _update_fields_message(interaction, slot_index=self.slot_index, section_key=self.section_key, status_message=status_message)

    class PatternDropdownSettingSelect(discord.ui.Select):
        def __init__(self, current_key: str):
            options = [
                discord.SelectOption(label="Shape", value="shape", default=(current_key == "shape")),
                discord.SelectOption(label="Size", value="size", default=(current_key == "size")),
                discord.SelectOption(label="Width", value="width", default=(current_key == "width")),
                discord.SelectOption(label="Turn", value="turn", default=(current_key == "turn")),
                discord.SelectOption(label="Turn Times", value="turn_times", default=(current_key == "turn_times")),
            ]
            super().__init__(placeholder="Pattern dropdown setting", min_values=1, max_values=1, options=options)

        async def callback(self, interaction: discord.Interaction):
            setting_key = self.values[0]
            await _update_fields_message(
                interaction,
                slot_index=self.view.slot_index,
                section_key=self.view.section_key,
                dropdown_key=setting_key,
            )

    class PatternDropdownValueSelect(discord.ui.Select):
        def __init__(self, setting_key: str, field_data: Dict):
            current_value = str(field_data.get(setting_key, ""))
            if setting_key == "shape":
                values = _get_available_patterns(current_shape=current_value)
                options = [discord.SelectOption(label=v, value=v, default=(v == current_value)) for v in values]
            elif setting_key == "size":
                options = [
                    discord.SelectOption(label=s.upper(), value=s, default=(s == current_value.lower()))
                    for s in ["xs", "s", "m", "l", "xl"]
                ]
            elif setting_key == "width":
                options = [
                    discord.SelectOption(label=str(v), value=str(v), default=(str(v) == current_value))
                    for v in range(1, 9)
                ]
            elif setting_key == "turn":
                turn_value = current_value.lower() if current_value else "none"
                options = [
                    discord.SelectOption(label="None", value="none", default=(turn_value == "none")),
                    discord.SelectOption(label="Left", value="left", default=(turn_value == "left")),
                    discord.SelectOption(label="Right", value="right", default=(turn_value == "right")),
                ]
            else:
                options = [
                    discord.SelectOption(label=str(v), value=str(v), default=(str(v) == current_value))
                    for v in [1, 2, 3, 4]
                ]

            self.setting_key = setting_key
            super().__init__(placeholder="Pattern dropdown value", min_values=1, max_values=1, options=options)

        async def callback(self, interaction: discord.Interaction):
            raw_value = self.values[0]
            save_value = raw_value
            if self.setting_key in {"width", "turn_times"}:
                save_value = int(raw_value)
            success, message = _save_slot_field_setting(self.view.slot_index, self.setting_key, save_value)
            await _update_fields_message(
                interaction,
                slot_index=self.view.slot_index,
                section_key=self.view.section_key,
                status_message=(message if success else f"Failed to update {self.setting_key}."),
                dropdown_key=self.setting_key,
            )

    class EditBasicFormButton(discord.ui.Button):
        def __init__(self, slot_index: int, section_key: str):
            self.slot_index = slot_index
            self.section_key = section_key
            super().__init__(label="Edit Basic Form", style=discord.ButtonStyle.primary)

        async def callback(self, interaction: discord.Interaction):
            settings = get_cached_settings()
            fields, fields_enabled = _get_field_slots(settings)
            field_map = _load_field_map()
            field_name = fields[self.slot_index]
            field_data = dict(field_map.get(field_name, {}))
            await interaction.response.send_modal(
                BasicFieldModal(
                    slot_index=self.slot_index,
                    section_key=self.section_key,
                    field_name=field_name,
                    task_enabled=fields_enabled[self.slot_index],
                    shift_lock=bool(field_data.get("shift_lock", False)),
                    drift=bool(field_data.get("field_drift_compensation", False)),
                    source_channel_id=interaction.channel_id,
                    source_message_id=(interaction.message.id if interaction.message else None),
                )
            )

    class EditPatternFormButton(discord.ui.Button):
        def __init__(self, slot_index: int, section_key: str):
            self.slot_index = slot_index
            self.section_key = section_key
            super().__init__(label="Edit Pattern Form", style=discord.ButtonStyle.primary)

        async def callback(self, interaction: discord.Interaction):
            settings = get_cached_settings()
            fields, _ = _get_field_slots(settings)
            field_map = _load_field_map()
            field_name = fields[self.slot_index]
            field_data = dict(field_map.get(field_name, {}))
            await interaction.response.send_modal(
                PatternFlagsModal(
                    self.slot_index,
                    self.section_key,
                    field_data,
                    source_channel_id=interaction.channel_id,
                    source_message_id=(interaction.message.id if interaction.message else None),
                )
            )

    class EditUntilFormButton(discord.ui.Button):
        def __init__(self, slot_index: int, section_key: str):
            self.slot_index = slot_index
            self.section_key = section_key
            super().__init__(label="Edit Until Form", style=discord.ButtonStyle.primary)

        async def callback(self, interaction: discord.Interaction):
            settings = get_cached_settings()
            fields, _ = _get_field_slots(settings)
            field_map = _load_field_map()
            field_name = fields[self.slot_index]
            field_data = dict(field_map.get(field_name, {}))
            await interaction.response.send_modal(
                UntilFieldModal(
                    self.slot_index,
                    self.section_key,
                    field_data,
                    source_channel_id=interaction.channel_id,
                    source_message_id=(interaction.message.id if interaction.message else None),
                )
            )

    class EditGooFormButton(discord.ui.Button):
        def __init__(self, slot_index: int, section_key: str):
            self.slot_index = slot_index
            self.section_key = section_key
            super().__init__(label="Edit Goo Form", style=discord.ButtonStyle.primary)

        async def callback(self, interaction: discord.Interaction):
            settings = get_cached_settings()
            fields, _ = _get_field_slots(settings)
            field_map = _load_field_map()
            field_name = fields[self.slot_index]
            field_data = dict(field_map.get(field_name, {}))
            await interaction.response.send_modal(
                GooFieldModal(
                    self.slot_index,
                    self.section_key,
                    field_data,
                    source_channel_id=interaction.channel_id,
                    source_message_id=(interaction.message.id if interaction.message else None),
                )
            )

    class FieldsPanelView(SettingsBaseView):
        def __init__(self, slot_index: int, section_key: str, requester_id: Optional[int], status_message: Optional[str] = None, dropdown_key: Optional[str] = None):
            super().__init__(requester_id=requester_id)
            self.slot_index = slot_index
            self.section_key = section_key
            self.status_message = status_message
            self.dropdown_key = dropdown_key

            settings = get_cached_settings()
            fields, _ = _get_field_slots(settings)
            field_map = _load_field_map()
            field_name = fields[slot_index]
            field_data = dict(field_map.get(field_name, {}))

            self.add_item(FieldsSlotSelect(current_slot=slot_index))
            self.add_item(FieldsSectionSelect(current_section=section_key))

            if section_key == "basic":
                self.add_item(FieldNameSelect(current_field=field_name))
                self.add_item(EditBasicFormButton(slot_index=slot_index, section_key=section_key))
            elif section_key == "pattern":
                current_pattern_key = dropdown_key or "shape"
                self.add_item(PatternDropdownSettingSelect(current_key=current_pattern_key))
                self.add_item(PatternDropdownValueSelect(setting_key=current_pattern_key, field_data=field_data))
                self.add_item(EditPatternFormButton(slot_index=slot_index, section_key=section_key))
            elif section_key == "until":
                self.add_item(FieldReturnSelect(current_return=str(field_data.get("return", "walk"))))
                self.add_item(EditUntilFormButton(slot_index=slot_index, section_key=section_key))
            elif section_key == "goo":
                self.add_item(EditGooFormButton(slot_index=slot_index, section_key=section_key))
            elif section_key == "start":
                self.add_item(FieldStartLocationSelect(current_location=str(field_data.get("start_location", "center"))))
                self.add_item(FieldDistanceSelect(current_distance=field_data.get("distance", 1)))

            self.add_item(RefreshFieldsButton(slot_index=slot_index, section_key=section_key))
            self.add_item(BackButton())

    class MacroModeSelect(discord.ui.Select):
        def __init__(self, settings: Dict):
            current = settings.get("macro_mode", "normal")
            options = []
            for value, label in MACRO_MODE_OPTIONS:
                options.append(discord.SelectOption(label=label, value=value, default=(value == current)))
            super().__init__(placeholder="Select macro mode", min_values=1, max_values=1, options=options)

        async def callback(self, interaction: discord.Interaction):
            mode = self.values[0]
            success, message = update_setting("macro_mode", mode)
            if success:
                try:
                    import eel
                    eel.updateMacroMode()
                except Exception:
                    pass
            status_message = message if success else "Failed to update macro mode."
            await _update_category_message(interaction, "macro_mode", status_message=status_message)

    class ToggleSettingsSelect(discord.ui.Select):
        def __init__(self, settings: Dict, setting_items: List[Tuple[str, str]], placeholder: str):
            options = []
            for key, label in setting_items:
                is_enabled = settings.get(key, False)
                options.append(discord.SelectOption(label=label, value=key, default=is_enabled))
            super().__init__(
                placeholder=placeholder,
                min_values=0,
                max_values=len(options),
                options=options,
            )
            self.setting_items = setting_items

        async def callback(self, interaction: discord.Interaction):
            selected = set(self.values)
            failures = []
            for key, _ in self.setting_items:
                success, _ = update_setting(key, key in selected)
                if not success:
                    failures.append(key)
            status_message = "Updated settings." if not failures else "Some settings failed to update."
            category_key = self.view.category_key if hasattr(self.view, "category_key") else "settings"
            await _update_category_message(interaction, category_key, status_message=status_message)

    class UtilityToggleSelect(discord.ui.Select):
        def __init__(self, settings: Dict):
            options = []
            for task_id, label in UTILITY_TASK_SETTINGS:
                options.append(
                    discord.SelectOption(
                        label=label,
                        value=task_id,
                        default=_is_task_toggle_enabled(task_id, settings),
                    )
                )
            super().__init__(placeholder="Select enabled utility tasks", min_values=0, max_values=len(options), options=options)

        async def callback(self, interaction: discord.Interaction):
            selected = set(self.values)
            settings = get_cached_settings()
            failures = []
            for task_id, _ in UTILITY_TASK_SETTINGS:
                success, _ = _set_task_toggle_enabled(task_id, task_id in selected, settings)
                if not success:
                    failures.append(task_id)
            status_message = "Updated utility settings." if not failures else "Some utility settings failed to update."
            await _update_category_message(interaction, "utility", status_message=status_message)

    class HiveSlotSelect(discord.ui.Select):
        def __init__(self, settings: Dict):
            current = settings.get("hive_number", 1)
            options = []
            for slot in range(1, 7):
                options.append(discord.SelectOption(label=str(slot), value=str(slot), default=(slot == current)))
            super().__init__(placeholder="Select hive slot", min_values=1, max_values=1, options=options)

        async def callback(self, interaction: discord.Interaction):
            slot = int(self.values[0])
            success, message = update_setting("hive_number", slot)
            if success and updateGUI is not None:
                updateGUI.value = 1
            status_message = message if success else "Failed to update hive slot."
            await _update_category_message(interaction, "hive_slot", status_message=status_message)

    class SettingsHomeView(SettingsBaseView):
        def __init__(self, requester_id: Optional[int]):
            super().__init__(requester_id=requester_id)
            self.add_item(CategorySelect())

    class SettingsCategoryView(SettingsBaseView):
        def __init__(self, category_key: str, requester_id: Optional[int], status_message: Optional[str] = None):
            super().__init__(requester_id=requester_id)
            self.category_key = category_key
            self.status_message = status_message
            settings = get_cached_settings()

            if category_key == "fields":
                self.add_item(OpenFieldsPanelButton())
            elif category_key == "macro_mode":
                self.add_item(MacroModeSelect(settings))
            elif category_key == "quests":
                self.add_item(ToggleSettingsSelect(settings, QUEST_SETTINGS, "Select enabled quests"))
            elif category_key == "collectibles":
                self.add_item(ToggleSettingsSelect(settings, COLLECTIBLE_SETTINGS, "Select enabled collectibles"))
            elif category_key == "mobs":
                self.add_item(ToggleSettingsSelect(settings, MOB_SETTINGS, "Select enabled mobs"))
            elif category_key == "utility":
                self.add_item(UtilityToggleSelect(settings))
            elif category_key == "hive_slot":
                self.add_item(HiveSlotSelect(settings))

            self.add_item(RefreshButton(category_key))
            self.add_item(BackButton())

    @bot.tree.command(name = "ping", description = "Check if the bot is online")
    async def ping(interaction: discord.Interaction):
        await interaction.response.send_message("Pong!")
    
    @bot.tree.command(name = "screenshot", description = "Send a screenshot of your screen")
    async def screenshot(interaction: discord.Interaction):
        await interaction.response.defer()
        img = screenshotRobloxWindow()
        with io.BytesIO() as imageBinary:
            img.save(imageBinary, "PNG")
            imageBinary.seek(0)
            await interaction.followup.send(file = discord.File(fp=imageBinary, filename="screenshot.png"))

    @bot.tree.command(name = "start", description = "Start")
    async def start(interaction: discord.Interaction):
        if run.value == 2: 
            await interaction.response.send_message("Macro is already running")
            return 
        try:
            # Press F1 to start the macro (simulating keyboard input)
            from pynput.keyboard import Controller, Key
            controller = Controller()
            controller.press(Key.f1)
            controller.release(Key.f1)
            await interaction.response.send_message("Starting Macro")
        except Exception as e:
            # Fallback to setting run.value if key press fails
            run.value = 1
            await interaction.response.send_message(f"Starting Macro. Error: {str(e)}")

    @bot.tree.command(name = "stop", description = "Stop the macro")
    async def stop(interaction: discord.Interaction):
        if run.value == 3:
            await interaction.response.send_message("Macro is already stopped")
            return
        try:
            # Press F3 to stop the macro (simulating keyboard input)
            from pynput.keyboard import Controller, Key
            controller = Controller()
            controller.press(Key.f3)
            controller.release(Key.f3)
            await interaction.response.send_message("Stopping Macro")
        except Exception as e:
            # Fallback to setting run.value if key press fails
            run.value = 0
            await interaction.response.send_message(f"Stopping Macro. Error: {str(e)}")

    @bot.tree.command(name = "pause", description = "Pause the macro")
    async def pause(interaction: discord.Interaction):
        if run.value == 6:
            await interaction.response.send_message("Macro is already paused")
            return
        if run.value in (0, 3):
            await interaction.response.send_message("Macro is not running")
            return

        run.value = 6
        await interaction.response.send_message("Macro Paused")

    @bot.tree.command(name = "resume", description = "Resume the macro")
    async def resume(interaction: discord.Interaction):
        if run.value == 2:
            await interaction.response.send_message("Macro is already running")
            return
        if run.value != 6:
            await interaction.response.send_message("Macro is not paused")
            return

        run.value = 2
        await interaction.response.send_message("Macro Resumed")

    @bot.tree.command(name = "rejoin", description = "Make the macro rejoin the game.")
    async def rejoin(interaction: discord.Interaction):
        run.value = 4
        await interaction.response.send_message("Macro is rejoining")

    @bot.tree.command(name = "reset", description = "Reset the character and return to hive")
    async def reset(interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            keyboard.releaseMovement()
            # Request reset in the macro process using a special run value
            import modules.macro as macroModule
            # Use a dummy queue if recentLogs is not a queue
            logQueue = recentLogs if hasattr(recentLogs, "put") else queue.Queue()
            macro = macroModule.macro(reset, logQueue, updateGUI)
            macro.status.value = ""
            if hasattr(macro, 'stopGather'):
                macro.stopGather()
            if hasattr(macro, 'logger') and hasattr(macro.logger, 'webhook'):
                macro.logger.webhook("", "Player died (Reset Command)", "dark brown", "screen", ping_category="ping_character_deaths")
            time.sleep(0.4)
            macro.reset(convert=True)
            await interaction.followup.send("✅ Reset completed.")
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to request reset: {str(e)}")
    
    @bot.tree.command(name = "logs", description = "Show recent macro actions (optionally specify count)")
    @app_commands.describe(count="Number of recent log entries to show (1-50)")
    async def show_logs(interaction: discord.Interaction, count: int = 10):
        """Show recent actions from the macro log (limit by `count`)"""
        try:
            if recentLogs is None or len(recentLogs) == 0:
                await interaction.response.send_message("📝 No recent macro logs available.")
                return

            embed = discord.Embed(title="📋 Recent Macro Actions", color=0x00ff00)

            # Validate and clamp requested count
            try:
                count = int(count)
            except Exception:
                count = 10

            if count < 1:
                count = 1
            if count > 50:
                count = 50

            # Get the last `count` logs (or fewer if not available)
            recent_actions = list(recentLogs)[-count:] if len(recentLogs) > count else list(recentLogs)

            log_text = ""
            for log_entry in recent_actions:
                time_str = log_entry.get('time', 'Unknown')
                title = log_entry.get('title', 'Unknown')
                desc = log_entry.get('desc', '')

                # Format the log entry
                if desc:
                    log_text += f"`{time_str}` **{title}** - {desc}\n"
                else:
                    log_text += f"`{time_str}` **{title}**\n"

            if log_text:
                # Ensure each embed field value is <= 1024 characters (Discord limit)
                if len(log_text) > 1024:
                    # Split by lines into chunks that fit within 1024 chars
                    lines = log_text.rstrip().splitlines(keepends=True)
                    chunks = []
                    current_chunk = ""
                    for line in lines:
                        if len(current_chunk) + len(line) > 1024:
                            if current_chunk:
                                chunks.append(current_chunk.rstrip())
                            current_chunk = line
                        else:
                            current_chunk += line

                    if current_chunk:
                        chunks.append(current_chunk.rstrip())

                    for i, chunk in enumerate(chunks):
                        field_name = f"Recent Actions (Part {i + 1})" if len(chunks) > 1 else "Recent Actions"
                        embed.add_field(name=field_name, value=chunk, inline=False)
                else:
                    embed.add_field(name="Recent Actions", value=log_text.rstrip(), inline=False)
            else:
                embed.add_field(name="Recent Actions", value="No actions to display", inline=False)

            embed.set_footer(text=f"Showing last {len(recent_actions)} actions")
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(f"❌ Error retrieving logs: {str(e)}")

    @bot.tree.command(name = "status", description = "Get the current macro status")
    async def get_status(interaction: discord.Interaction):
        status_messages = {
            0: "⏹️ Stopping",
            1: "▶️ Starting",
            2: "✅ Running",
            3: "⏹️ Stopped",
            4: "🔄 Disconnected/Rejoining",
            6: "⏸️ Paused"
        }

        macro_status = status_messages.get(run.value, "❓ Unknown")
        current_task = status.value if hasattr(status, 'value') and status.value else "None"

        # Color: green for running, orange for paused, red for stopped/other
        if run.value == 2:
            embed_color = 0x00ff00  # Green
        elif run.value == 6:
            embed_color = 0xffa500  # Orange for paused
        else:
            embed_color = 0xff0000  # Red

        embed = discord.Embed(title="📊 Macro Status", color=embed_color)
        embed.add_field(name="State", value=macro_status, inline=True)
        embed.add_field(name="Current Task", value=current_task.replace('_', ' ').title(), inline=True)
        
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="tasklist", description="Show enabled task order with current and next task")
    async def tasklist(interaction: discord.Interaction):
        try:
            settings = get_cached_settings()
            queue_order = _get_task_list_order(settings)
            enabled_tasks = _get_enabled_task_order(settings)

            current_task_raw = status.value if hasattr(status, 'value') and status.value else ""
            current_task_id = _normalize_current_task_to_priority_task(current_task_raw, settings, queue_order)

            next_task_id = None
            if enabled_tasks:
                if current_task_id in enabled_tasks:
                    current_index = enabled_tasks.index(current_task_id)
                    next_task_id = enabled_tasks[(current_index + 1) % len(enabled_tasks)]
                else:
                    next_task_id = enabled_tasks[0]

            mode_label = {
                "normal": "Normal",
                "quest": "Quests",
                "field": "Field",
            }.get(settings.get("macro_mode", "normal"), settings.get("macro_mode", "normal"))

            if not enabled_tasks:
                embed = discord.Embed(
                    title="📋 Macro Task List",
                    description="No enabled tasks found for the current configuration.",
                    color=0xffa500,
                )
                embed.add_field(name="Macro Mode", value=mode_label, inline=True)
                embed.add_field(name="Current Task", value=current_task_raw.replace('_', ' ').title() or "None", inline=True)
                await interaction.response.send_message(embed=embed)
                return

            task_lines = []
            for i, task_id in enumerate(enabled_tasks, start=1):
                marker = "•"
                if task_id == current_task_id and task_id == next_task_id:
                    marker = "🟢⏭️"
                elif task_id == current_task_id:
                    marker = "🟢"
                elif task_id == next_task_id:
                    marker = "⏭️"
                task_lines.append(f"{marker} {i}. {_format_task_name(task_id)}")

            embed = discord.Embed(
                title="📋 Macro Task List",
                description="\n".join(task_lines),
                color=0x00ff00,
            )
            embed.add_field(name="Macro Mode", value=mode_label, inline=True)
            embed.add_field(name="Enabled Tasks", value=str(len(enabled_tasks)), inline=True)
            embed.add_field(name="Current", value=_format_task_name(current_task_id) if current_task_id else (current_task_raw.replace('_', ' ').title() or "None"), inline=False)
            embed.add_field(name="Next", value=_format_task_name(next_task_id) if next_task_id else "None", inline=False)
            embed.set_footer(text="Legend: 🟢 current task, ⏭️ next task")

            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error retrieving task list: {str(e)}")

    @bot.tree.command(name="nectar", description="Show current nectar percentages (current + estimated)")
    async def show_nectar(interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            # Create a buff detector to read nectar values from screen
            from modules.screen.robloxWindow import RobloxWindowBounds
            from modules.submacros.hourlyReport import BuffDetector
            import json as _json

            robloxWindow = RobloxWindowBounds()
            try:
                robloxWindow.setRobloxWindowBounds()
            except Exception:
                # proceed — setRobloxWindowBounds may fail if window not found
                pass

            bd = BuffDetector(robloxWindow)

            # Get current nectar values
            import modules.macro as macroModule
            nectar_names = getattr(macroModule, 'nectarNames', ["comforting","refreshing","satisfying","motivating","invigorating"])
            current_vals = {}
            for n in nectar_names:
                try:
                    current_vals[n] = round(float(bd.getNectar(n)), 1)
                except Exception:
                    current_vals[n] = 0.0

            # Get estimated nectar percents from auto_planters.json
            estimates = {n: 0.0 for n in nectar_names}
            try:
                with open("./data/user/auto_planters.json","r") as f:
                    ap = _json.load(f)
                    planters = ap.get('planters', [])
                for p in planters:
                    nectar = p.get('nectar')
                    if nectar in estimates:
                        try:
                            estimates[nectar] += float(p.get('nectar_est_percent', 0))
                        except Exception:
                            pass
            except Exception:
                pass

            # Build embed
            desc_lines = []
            for n in nectar_names:
                cur = current_vals.get(n, 0.0)
                est = estimates.get(n, 0.0)
                total = round(cur + est, 1)
                desc_lines.append(f"**{n.title()}**: {cur}% (est +{est}%) → Total: {total}%")

            embed = discord.Embed(title="🍯 Nectar Percentages", description="\n".join(desc_lines), color=0x00ff00)

            # Attach a screenshot of the game window if possible
            try:
                from modules.screen.screenshot import screenshotRobloxWindow
                # Take screenshot and overlay nectar percentages for clarity
                img = screenshotRobloxWindow()
                try:
                    from PIL import ImageDraw, ImageFont
                    import io as _io
                    # Build text overlay
                    draw = ImageDraw.Draw(img)
                    try:
                        font = ImageFont.truetype("/Library/Fonts/Arial.ttf", 20)
                    except Exception:
                        font = ImageFont.load_default()

                    # collect nectar values (use BuffDetector logic)
                    from modules.screen.robloxWindow import RobloxWindowBounds
                    from modules.submacros.hourlyReport import BuffDetector
                    robloxWindow = RobloxWindowBounds()
                    try:
                        robloxWindow.setRobloxWindowBounds()
                    except Exception:
                        pass
                    bd = BuffDetector(robloxWindow)

                    nectar_names = getattr(__import__("modules.macro", fromlist=["nectarNames"]), 'nectarNames', ["comforting","refreshing","satisfying","motivating","invigorating"])
                    lines = []
                    for i, n in enumerate(nectar_names):
                        try:
                            val = round(float(bd.getNectar(n)), 1)
                        except Exception:
                            val = 0.0
                        lines.append(f"{n.title()}: {val}%")

                    # Draw background rectangle
                    padding = 8
                    line_h = font.getsize("Tg")[1] + 4
                    box_w = max(font.getsize(l)[0] for l in lines) + padding*2
                    box_h = line_h * len(lines) + padding*2
                    draw.rectangle([(10,10),(10+box_w,10+box_h)], fill=(0,0,0,180))
                    for idx, l in enumerate(lines):
                        draw.text((10+padding, 10+padding + idx*line_h), l, font=font, fill=(255,255,255))

                    with _io.BytesIO() as imageBinary:
                        img.save(imageBinary, "PNG")
                        imageBinary.seek(0)
                        await interaction.followup.send(embed=embed, file=discord.File(fp=imageBinary, filename="nectar.png"))
                except Exception:
                    # Fallback to sending raw screenshot if overlay fails
                    with io.BytesIO() as imageBinary:
                        img.save(imageBinary, "PNG")
                        imageBinary.seek(0)
                        await interaction.followup.send(embed=embed, file=discord.File(fp=imageBinary, filename="nectar.png"))
            except Exception:
                # Fallback to sending without image
                await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.response.send_message(f"❌ Error reading nectar: {str(e)}")

    @bot.tree.command(name = "amulet", description = "Choose to keep or replace an amulet")
    @app_commands.describe(option = "keep or replace an amulet")
    async def amulet(interaction: discord.Interaction, option: str):
        if run.value != 2:
            await interaction.response.send_message("Macro is not running")
        option = option.lower()
        keepAlias = ["k", "keep"]
        replaceAlias = ["r", "replace"]
        if not option in keepAlias and not option in replaceAlias:
            await interaction.response.send_message("Unknown option. Enter either `keep` or `replace`")
        
        elif status.value != "amulet_wait":
            await interaction.response.send_message("There is no amulet to keep or replace")
            return
        elif option in keepAlias:
            status.value = "amulet_keep"
            await interaction.response.send_message("Keeping amulet")
        elif option in replaceAlias:
            status.value = "amulet_replace"
            await interaction.response.send_message("Replacing amulet")

    @bot.tree.command(name = "battery", description = "Get your current battery status")
    async def battery(interaction: discord.Interaction):
        try:
            output = subprocess.check_output(["pmset", "-g", "batt"], text=True)
            for line in output.split("\n"):
                if "InternalBattery" in line:
                    parts = line.split("\t")[-1].split(";")
                    percent = parts[0].strip()
                    status = parts[1].strip()
                    await interaction.response.send_message(f"Battery is at {percent} and is currently {status}.")
                    return
            
            await interaction.response.send_message("Battery information not found.")
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}")
    
    @bot.tree.command(name = "close", description = "Close the macro and/or Roblox")
    @app_commands.describe(action="What to close: both, roblox, macro")
    @app_commands.choices(action=[
        app_commands.Choice(name="Both", value="both"),
        app_commands.Choice(name="Roblox only", value="roblox"),
        app_commands.Choice(name="Macro only", value="macro"),
    ])
    async def close(interaction: discord.Interaction, action: str = "both"):
        """Close macro and/or Roblox depending on chosen action."""
        try:
            if action == "both":
                run.value = 0
                closeApp("Roblox")
                await interaction.response.send_message("Closing macro and Roblox...")
                os.kill(os.getppid(), signal.SIGTERM)
            elif action == "roblox":
                closeApp("Roblox")
                await interaction.response.send_message("Closing Roblox...")
            elif action == "macro":
                # stop the macro loop but keep the bot running
                run.value = 0
                await interaction.response.send_message("Stopping macro (Roblox will remain open).")
                os.kill(os.getppid(), signal.SIGTERM)
            else:
                await interaction.response.send_message("❌ Unknown action. Use: both, roblox, or macro")
        except Exception as e:
            await interaction.response.send_message(f"❌ Error performing close action: {str(e)}")

    def _set_macos_mute(muted: bool) -> None:
        """Set macOS system audio mute state using AppleScript via osascript."""
        try:
            if sys.platform != "darwin":
                raise OSError("Not running on macOS")
            state = "true" if muted else "false"
            # Use osascript to set the output muted state
            subprocess.check_call(["osascript", "-e", f'set volume output muted {state}' ])
        except Exception:
            raise

    @bot.tree.command(name = "mute", description = "Mute system audio (macOS only)")
    async def mute_audio(interaction: discord.Interaction):
        try:
            if sys.platform != "darwin":
                await interaction.response.send_message("❌ This command only works on macOS.")
                return
            _set_macos_mute(True)
            await interaction.response.send_message("🔇 System audio muted.")
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to mute audio: {e}")

    @bot.tree.command(name = "unmute", description = "Unmute system audio (macOS only)")
    async def unmute_audio(interaction: discord.Interaction):
        try:
            if sys.platform != "darwin":
                await interaction.response.send_message("❌ This command only works on macOS.")
                return
            _set_macos_mute(False)
            await interaction.response.send_message("🔊 System audio unmuted.")
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to unmute audio: {e}")
    
    @bot.tree.command(name = "disablegoo", description = "Disable goo for a specific field")
    async def disable_goo(interaction: discord.Interaction, field: str):
        print("disablegoo command called")
        try:
            # Import the settings functions
            from modules.misc.settingsManager import loadFields, saveField
            
            # Load current field settings
            fieldSettings = loadFields()
            
            # Normalize field name (lowercase, handle spaces)
            fieldKey = field.lower().strip()
            
            # Check if field exists
            if fieldKey not in fieldSettings:
                await interaction.response.send_message(f"Field '{field}' not found. Available fields: {', '.join(fieldSettings.keys())}")
                return
            
            # Disable goo for the field
            fieldSettings[fieldKey]["goo"] = False
            
            # Save the updated settings
            saveField(fieldKey, fieldSettings[fieldKey])
            
            await interaction.response.send_message(f"✅ Goo disabled for field: {fieldKey.title()}")
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Error disabling goo: {str(e)}")
    
    @bot.tree.command(name = "enablegoo", description = "Enable goo for a specific field")
    async def enable_goo(interaction: discord.Interaction, field: str):
        print("enablegoo command called")
        try:
            # Import the settings functions
            from modules.misc.settingsManager import loadFields, saveField
            
            # Load current field settings
            fieldSettings = loadFields()
            
            # Normalize field name (lowercase, handle spaces)
            fieldKey = field.lower().strip()
            
            # Check if field exists
            if fieldKey not in fieldSettings:
                await interaction.response.send_message(f"Field '{field}' not found. Available fields: {', '.join(fieldSettings.keys())}")
                return
            
            # Enable goo for the field
            fieldSettings[fieldKey]["goo"] = True
            
            # Save the updated settings
            saveField(fieldKey, fieldSettings[fieldKey])
            
            await interaction.response.send_message(f"✅ Goo enabled for field: {fieldKey.title()}")
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Error enabling goo: {str(e)}")
    
    @bot.tree.command(name = "goostatus", description = "Check goo status for all fields")
    async def goo_status(interaction: discord.Interaction):
        print("goostatus command called")
        try:
            # Import the settings functions
            from modules.misc.settingsManager import loadFields

            # Load current field settings
            fieldSettings = loadFields()

            # Create status message
            statusMessage = "**Goo Status for All Fields:**\n"
            enabledFields = []
            disabledFields = []

            for fieldName, settings in fieldSettings.items():
                if settings.get("goo", False):
                    enabledFields.append(fieldName.title())
                else:
                    disabledFields.append(fieldName.title())

            if enabledFields:
                statusMessage += f"✅ **Enabled:** {', '.join(enabledFields)}\n"
            if disabledFields:
                statusMessage += f"❌ **Disabled:** {', '.join(disabledFields)}\n"

            await interaction.response.send_message(statusMessage)

        except Exception as e:
            await interaction.response.send_message(f"❌ Error checking goo status: {str(e)}")

    async def profile_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice]:
        """Auto-complete function for profile names"""
        try:
            profiles = settingsManager.listProfiles()
            choices = []
            for profile in profiles:
                if current.lower() in profile.lower():
                    choices.append(app_commands.Choice(name=profile.title(), value=profile))
            return choices[:25]  # Discord limit is 25 choices
        except Exception:
            return []

    @bot.tree.command(name="swapprofile", description="Swap to a different profile (macro must be stopped)")
    @app_commands.describe(profile="Profile name to switch to")
    @app_commands.autocomplete(profile=profile_autocomplete)
    async def swap_profile(interaction: discord.Interaction, profile: str):
        """Swap to a different profile. Only works when macro is stopped."""
        try:
            # Check if macro is stopped
            if run.value != 3:
                status_map = {
                    0: "Stopping",
                    1: "Starting",
                    2: "Running",
                    4: "Disconnected/Rejoining",
                    6: "Paused"
                }
                current_status = status_map.get(run.value, "Unknown")
                await interaction.response.send_message(
                    f"❌ Cannot swap profiles while macro is {current_status.lower()}. "
                    f"Please stop the macro first using `/stop` or pressing F3."
                )
                return

            # Attempt profile switch
            success, message = settingsManager.switchProfile(profile)
            if success:
                # Clear settings cache to reload new profile settings
                clear_settings_cache()
                # Update the GUI to reflect the new profile's settings
                if updateGUI is not None:
                    updateGUI.value = 1
                await interaction.response.send_message(f"✅ {message}")
            else:
                await interaction.response.send_message(f"❌ {message}")

        except Exception as e:
            await interaction.response.send_message(f"❌ Error swapping profile: {str(e)}")

    @bot.tree.command(name = "streamurl", description = "Get the current stream URL")
    async def stream_url(interaction: discord.Interaction):
        try:
            # Read stream URL from file (use absolute path for reliability)
            import sys
            src_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            stream_url_file = os.path.join(src_dir, 'stream_url.txt')
            if os.path.exists(stream_url_file):
                with open(stream_url_file, 'r') as f:
                    stream_url = f.read().strip()
                if stream_url:
                    await interaction.response.send_message(f"🔗 **Current Stream URL:**\n{stream_url}")
                else:
                    await interaction.response.send_message("❌ No active stream URL found. Make sure streaming is enabled and running.")
            else:
                await interaction.response.send_message("❌ No active stream URL found. Make sure streaming is enabled and running.")

        except Exception as e:
            await interaction.response.send_message(f"❌ Error getting stream URL: {str(e)}")


    @bot.tree.command(name="privateserver", description="Get or set the configured private server link")
    @app_commands.describe(link="Private server link to save (optional)")
    async def private_server(interaction: discord.Interaction, link: Optional[str] = None):
        """Get the private server link or set it when `link` is provided."""
        try:
            settings = get_cached_settings()
            # If no link argument provided, just display current setting
            if link is None:
                stored = settings.get("private_server_link", "")
                if stored and str(stored).strip():
                    await interaction.response.send_message(f"🔗 **Private Server Link:**\n{stored}")
                else:
                    await interaction.response.send_message("❌ No private server link is configured.")
                return

            # Validate 'share?code' style links when using deeplink rejoin method
            if "share" in link and settings.get("rejoin_method") == "deeplink":
                await interaction.response.send_message(
                    "❌ You entered a 'share?code' private server link!\n\nTo fix this:\n1. Paste the link in your browser\n2. Wait for roblox to load in\n3. Copy the link from the top of your browser.  It should now be a 'privateServerLinkCode' link",
                    ephemeral=True,
                )
                return

            success, message = update_setting("private_server_link", link)
            if success:
                await interaction.response.send_message(f"✅ Private server link updated.\n🔗 {link}")
            else:
                await interaction.response.send_message(message)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error retrieving/updating private server link: {str(e)}")

    # === COMPREHENSIVE SETTINGS MANAGEMENT COMMANDS ===

    @bot.tree.command(name="settings", description="Open the settings panel")
    async def view_settings(interaction: discord.Interaction):
        """Open the interactive settings panel"""
        try:
            settings = get_cached_settings()
            view = SettingsHomeView(requester_id=interaction.user.id if interaction.user else None)
            embed = _build_overview_embed(settings)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error opening settings panel: {str(e)}", ephemeral=True)


    # === FIELD CONFIGURATION COMMANDS ===

    @bot.tree.command(name="fields", description="View field configuration")
    async def view_fields(interaction: discord.Interaction):
        """View current field configuration"""
        await interaction.response.defer()

        try:
            settings = get_cached_settings()
            field_list = settings.get("fields", [])
            fields_enabled = settings.get("fields_enabled", [])

            embed = discord.Embed(title="🌾 Field Configuration", color=0x00ff00)

            enabled_fields = []
            disabled_fields = []

            for i, field_name in enumerate(field_list):
                is_enabled = i < len(fields_enabled) and fields_enabled[i]

                if is_enabled:
                    enabled_fields.append(f"**{field_name.title()}**")
                else:
                    disabled_fields.append(field_name.title())

            if enabled_fields:
                embed.add_field(name="✅ **Enabled Fields**", value="\n".join(enabled_fields), inline=False)
            if disabled_fields:
                embed.add_field(name="❌ **Disabled Fields**", value=", ".join(disabled_fields), inline=False)

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"❌ Error retrieving field settings: {str(e)}")

    async def field_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice]:
        """Auto-complete function for currently active field names"""
        settings = get_cached_settings()
        field_list = settings.get("fields", [])
        choices = []

        for field in field_list:
            if current.lower() in field.lower():
                choices.append(app_commands.Choice(name=field.title(), value=field.lower().replace(" ", "_")))

        return choices[:25]  # Discord limit is 25 choices

    async def all_fields_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice]:
        """Auto-complete function for all possible field names"""
        # All possible field names in the game
        all_possible_fields = [
            "sunflower", "dandelion", "mushroom", "blue flower", "clover", "strawberry",
            "spider", "bamboo", "pineapple", "stump", "cactus", "pumpkin", "pine tree",
            "rose", "mountain top", "pepper", "coconut"
        ]
        choices = []

        for field in all_possible_fields:
            display_name = field.replace("_", " ").title()
            if current.lower() in field.lower() or current.lower() in display_name.lower():
                choices.append(app_commands.Choice(name=display_name, value=field))

        return choices[:25]  # Discord limit is 25 choices

    async def quest_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice]:
        """Auto-complete function for quest names"""
        quests = ["polar_bear", "brown_bear", "honey_bee", "bucko_bee", "riley_bee", "black_bear"]
        choices = []

        for quest in quests:
            if current.lower() in quest.lower():
                choices.append(app_commands.Choice(name=quest.replace("_", " ").title(), value=quest))

        return choices[:25]

    async def collectible_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice]:
        """Auto-complete function for collectible names"""
        collectibles = [
            "wealth_clock", "blueberry", "strawberry", "coconut", "royal_jelly", "ant_pass",
            "treat", "glue", "honeystorm"
        ]
        choices = []

        for collectible in collectibles:
            display_name = collectible.replace("_", " ").title()
            if current.lower() in collectible.lower():
                choices.append(app_commands.Choice(name=display_name, value=collectible))

        return choices[:25]

    async def mob_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice]:
        """Auto-complete function for mob names"""
        mobs = ["ladybug", "rhinobeetle", "scorpion", "mantis", "spider", "werewolf", "coconut_crab", "king_beetle", "tunnel_bear", "stump_snail"]
        choices = []

        for mob in mobs:
            display_name = mob.replace("_", " ").title()
            if current.lower() in mob.lower():
                choices.append(app_commands.Choice(name=display_name, value=mob))

        return choices[:25]

    async def planter_mode_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice]:
        """Auto-complete function for planter modes"""
        modes = [
            app_commands.Choice(name="Disabled", value="0"),
            app_commands.Choice(name="Manual", value="1"),
            app_commands.Choice(name="Auto", value="2")
        ]
        return modes

    async def use_when_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice]:
        """Auto-complete function for hotbar use_when options"""
        options = [
            app_commands.Choice(name="Never", value="never"),
            app_commands.Choice(name="Always", value="always"),
            app_commands.Choice(name="Field", value="field"),
            app_commands.Choice(name="Quest", value="quest")
        ]
        return options

    async def format_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice]:
        """Auto-complete function for time format options"""
        formats = [
            app_commands.Choice(name="Seconds", value="secs"),
            app_commands.Choice(name="Minutes", value="mins"),
            app_commands.Choice(name="Hours", value="hours")
        ]
        return formats

    async def boolean_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice]:
        """Auto-complete function for boolean values"""
        booleans = [
            app_commands.Choice(name="True", value="true"),
            app_commands.Choice(name="False", value="false")
        ]
        return booleans

    @bot.tree.command(name="field", description="Enable or disable a specific field")
    @app_commands.describe(field="Field name", enabled="Enable or disable")
    @app_commands.autocomplete(field=field_autocomplete, enabled=boolean_autocomplete)
    async def set_field(interaction: discord.Interaction, field: str, enabled: str):
        """Enable or disable a specific field"""
        try:
            field = field.lower().replace(" ", "_")
            enabled = enabled.lower() == "true"
            settings = get_cached_settings()

            field_list = settings.get("fields", [])
            fields_enabled = settings.get("fields_enabled", [])
            normalized_fields = [f.lower().replace(" ", "_") for f in field_list]

            if field not in normalized_fields:
                await interaction.response.send_message(
                    f"❌ Field '{field}' not found. Available fields: {', '.join([f.replace('_', ' ').title() for f in normalized_fields])}"
                )
                return

            field_index = normalized_fields.index(field)

            if field_index < len(fields_enabled):
                fields_enabled[field_index] = enabled
                update_setting("fields_enabled", fields_enabled)
                state = "Enabled" if enabled else "Disabled"
                await interaction.response.send_message(f"✅ {state} field: {field_list[field_index].title()}")
            else:
                await interaction.response.send_message("❌ Field index out of range")

        except Exception as e:
            await interaction.response.send_message(f"❌ Error updating field: {str(e)}")

    @bot.tree.command(name="swapfield", description="Swap one field for another")
    @app_commands.describe(current="Current field to replace (e.g., pine_tree)", new="New field to use (e.g., rose)")
    @app_commands.autocomplete(current=field_autocomplete, new=all_fields_autocomplete)
    async def swap_field(interaction: discord.Interaction, current: str, new: str):
        """Swap one field for another in the active fields list"""
        try:
            current_field = current.lower().replace(" ", "_")
            new_field = new.lower().replace(" ", "_")

            settings = get_cached_settings()

            # Get the fields list and fields_enabled array
            field_list = settings.get("fields", [])
            fields_enabled = settings.get("fields_enabled", [])

            # Normalize field names for comparison
            normalized_fields = [f.lower().replace(" ", "_") for f in field_list]

            # Check if current field exists
            if current_field not in normalized_fields:
                available = ', '.join([f.replace('_', ' ').title() for f in normalized_fields])
                await interaction.response.send_message(f"❌ Current field '{current}' not found. Available fields: {available}")
                return

            # Find the field index
            field_index = normalized_fields.index(current_field)

            # Update the field in the list
            original_field_name = field_list[field_index]
            field_list[field_index] = new_field

            # Save the updated fields list
            update_setting("fields", field_list)

            await interaction.response.send_message(f"✅ Swapped field: **{original_field_name.title()}** → **{new_field.replace('_', ' ').title()}**")

        except Exception as e:
            await interaction.response.send_message(f"❌ Error swapping field: {str(e)}")

    # === QUEST MANAGEMENT COMMANDS ===

    @bot.tree.command(name="quests", description="View quest configuration")
    async def view_quests(interaction: discord.Interaction):
        """View current quest configuration"""
        try:
            settings = get_cached_settings()

            quest_settings = {
                "🐻 **Polar Bear**": settings.get("polar_bear_quest", False),
                "🐻 **Brown Bear**": settings.get("brown_bear_quest", False),
                "🐻 **Black Bear**": settings.get("black_bear_quest", False),
                "🍯 **Honey Bee**": settings.get("honey_bee_quest", False),
                "🐝 **Bucko Bee**": settings.get("bucko_bee_quest", False),
                "🎯 **Riley Bee**": settings.get("riley_bee_quest", False),
                "💧 **Use Gumdrops**": settings.get("quest_use_gumdrops", False)
            }

            embed = discord.Embed(title="📜 Quest Configuration", color=0x00ff00)

            for quest, enabled in quest_settings.items():
                status = "✅ Enabled" if enabled else "❌ Disabled"
                embed.add_field(name=quest, value=status, inline=True)

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(f"❌ Error retrieving quest settings: {str(e)}")

    @bot.tree.command(name="quest", description="Enable or disable a specific quest")
    @app_commands.describe(quest="Quest name (polar_bear, brown_bear, black_bear, honey_bee, bucko_bee, riley_bee)", enabled="Enable or disable")
    @app_commands.autocomplete(quest=quest_autocomplete, enabled=boolean_autocomplete)
    async def set_quest(interaction: discord.Interaction, quest: str, enabled: str):
        """Enable or disable a specific quest"""
        quest_mapping = {
            "polar_bear": "polar_bear_quest",
            "brown_bear": "brown_bear_quest",
            "black_bear": "black_bear_quest",
            "honey_bee": "honey_bee_quest",
            "bucko_bee": "bucko_bee_quest",
            "riley_bee": "riley_bee_quest"
        }

        quest_key = quest_mapping.get(quest.lower())
        if not quest_key:
            await interaction.response.send_message("❌ Invalid quest name. Use: polar_bear, brown_bear, black_bear, honey_bee, bucko_bee, or riley_bee")
            return

        success, message = update_setting(quest_key, enabled.lower() == "true")
        await interaction.response.send_message(message)

    # === COLLECTIBLES MANAGEMENT COMMANDS ===

    @bot.tree.command(name="collectibles", description="View collectibles configuration")
    async def view_collectibles(interaction: discord.Interaction):
        """View current collectibles configuration"""
        try:
            settings = get_cached_settings()

            collectible_settings = {
                "🕒 **Wealth Clock**": settings.get("wealth_clock", False),
                "🫐 **Blueberry Dispenser**": settings.get("blueberry_dispenser", False),
                "🍓 **Strawberry Dispenser**": settings.get("strawberry_dispenser", False),
                "🥥 **Coconut Dispenser**": settings.get("coconut_dispenser", False),
                "👑 **Royal Jelly Dispenser**": settings.get("royal_jelly_dispenser", False),
                "🎫 **Ant Pass Dispenser**": settings.get("ant_pass_dispenser", False),
                "🍬 **Treat Dispenser**": settings.get("treat_dispenser", False),
                "🧪 **Glue Dispenser**": settings.get("glue_dispenser", False),
                "🟧 **Honey Storm**": settings.get("honeystorm", False)
            }

            embed = discord.Embed(title="🎁 Collectibles Configuration", color=0x00ff00)

            enabled = []
            disabled = []

            for collectible, is_enabled in collectible_settings.items():
                if is_enabled:
                    enabled.append(collectible)
                else:
                    disabled.append(collectible)

            if enabled:
                embed.add_field(name="✅ **Enabled**", value="\n".join(enabled), inline=False)
            if disabled:
                embed.add_field(name="❌ **Disabled**", value="\n".join(disabled), inline=False)

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(f"❌ Error retrieving collectible settings: {str(e)}")

    @bot.tree.command(name="collectible", description="Enable or disable a specific collectible")
    @app_commands.describe(collectible="Collectible name", enabled="Enable or disable")
    @app_commands.autocomplete(collectible=collectible_autocomplete, enabled=boolean_autocomplete)
    async def set_collectible(interaction: discord.Interaction, collectible: str, enabled: str):
        """Enable or disable a specific collectible"""
        collectible_mapping = {
            "wealth_clock": "wealth_clock",
            "blueberry": "blueberry_dispenser",
            "strawberry": "strawberry_dispenser",
            "coconut": "coconut_dispenser",
            "royal_jelly": "royal_jelly_dispenser",
            "ant_pass": "ant_pass_dispenser",
            "treat": "treat_dispenser",
            "glue": "glue_dispenser",
            "honeystorm": "honeystorm"
        }

        collectible_key = collectible_mapping.get(collectible.lower().replace(" ", "_"))
        if not collectible_key:
            await interaction.response.send_message("❌ Invalid collectible name")
            return

        success, message = update_setting(collectible_key, enabled.lower() == "true")
        await interaction.response.send_message(message)

    # === PLANTER MANAGEMENT COMMANDS ===
    '''
    @bot.tree.command(name="planters", description="View planter configuration")
    async def view_planters(interaction: discord.Interaction):
        """View current planter configuration"""
        try:
            settings = get_cached_settings()

            embed = discord.Embed(title="🌱 Planter Configuration", color=0x00ff00)

            # Planter mode
            mode = settings.get("planters_mode", 0)
            mode_text = {0: "Disabled", 1: "Manual", 2: "Auto"}.get(mode, "Unknown")
            embed.add_field(name="🎛️ **Mode**", value=mode_text, inline=True)

            # Auto planter settings
            if mode == 2:
                embed.add_field(name="🔢 **Max Planters**", value=settings.get("auto_max_planters", 3), inline=True)
                embed.add_field(name="🎨 **Preset**", value=settings.get("auto_preset", "blue"), inline=True)

                # Show priority settings
                priority_text = []
                for i in range(5):
                    nectar = settings.get(f"auto_priority_{i}_nectar", "none")
                    min_val = settings.get(f"auto_priority_{i}_min", 0)
                    if nectar != "none":
                        priority_text.append(f"#{i+1}: {nectar} ({min_val}%)")

                embed.add_field(name="📊 **Nectar Priorities**", value="\n".join(priority_text) if priority_text else "None", inline=False)

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(f"❌ Error retrieving planter settings: {str(e)}")

    @bot.tree.command(name="setplantermode", description="Set planter mode (0=disabled, 1=manual, 2=auto)")
    @app_commands.describe(mode="Planter mode (0=disabled, 1=manual, 2=auto)")
    @app_commands.autocomplete(mode=planter_mode_autocomplete)
    async def set_planter_mode(interaction: discord.Interaction, mode: int):
        """Set planter mode"""
        if mode not in [0, 1, 2]:
            await interaction.response.send_message("❌ Invalid mode. Use 0 (disabled), 1 (manual), or 2 (auto)")
            return

        success, message = update_setting("planters_mode", mode)
        await interaction.response.send_message(message)

    @bot.tree.command(name="setmaxplanters", description="Set maximum number of auto planters")
    @app_commands.describe(count="Maximum number of planters (1-3)")
    async def set_max_planters(interaction: discord.Interaction, count: int):
        """Set maximum number of auto planters"""
        if count < 1 or count > 3:
            await interaction.response.send_message("❌ Count must be between 1 and 3")
            return

        success, message = update_setting("auto_max_planters", count)
        await interaction.response.send_message(message)
    '''
    # === MOB RUN COMMANDS ===

    @bot.tree.command(name="mobs", description="View mob run configuration")
    async def view_mobs(interaction: discord.Interaction):
        """View current mob run configuration"""
        try:
            settings = get_cached_settings()

            mob_settings = {
                "🐞 **Ladybug**": settings.get("ladybug", False),
                "🪲 **Rhinobeetle**": settings.get("rhinobeetle", False),
                "🦂 **Scorpion**": settings.get("scorpion", False),
                "🦗 **Mantis**": settings.get("mantis", False),
                "🕷️ **Spider**": settings.get("spider", False),
                "🐺 **Werewolf**": settings.get("werewolf", False),
                "🦀 **Coconut Crab**": settings.get("coconut_crab", False),
                "🪲 **King Beetle**": settings.get("king_beetle", False),
                "🐻 **Tunnel Bear**": settings.get("tunnel_bear", False),
                "🐌 **Stump Snail**": settings.get("stump_snail", False)
            }

            embed = discord.Embed(title="🐛 Mob Run Configuration", color=0x00ff00)

            enabled = []
            disabled = []

            for mob, is_enabled in mob_settings.items():
                if is_enabled:
                    enabled.append(mob)
                else:
                    disabled.append(mob)

            if enabled:
                embed.add_field(name="✅ **Enabled**", value="\n".join(enabled), inline=False)
            if disabled:
                embed.add_field(name="❌ **Disabled**", value="\n".join(disabled), inline=False)

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(f"❌ Error retrieving mob settings: {str(e)}")

    @bot.tree.command(name="mob", description="Enable or disable a specific mob run")
    @app_commands.describe(mob="Mob name", enabled="Enable or disable")
    @app_commands.autocomplete(mob=mob_autocomplete, enabled=boolean_autocomplete)
    async def set_mob(interaction: discord.Interaction, mob: str, enabled: str):
        """Enable or disable a specific mob run"""
        mob_mapping = {
            "ladybug": "ladybug",
            "rhinobeetle": "rhinobeetle",
            "scorpion": "scorpion",
            "mantis": "mantis",
            "spider": "spider",
            "werewolf": "werewolf",
            "coconut_crab": "coconut_crab",
            "king_beetle": "king_beetle",
            "tunnel_bear": "tunnel_bear",
            "stump_snail": "stump_snail"
        }

        mob_key = mob_mapping.get(mob.lower().replace(" ", "_"))
        if not mob_key:
            await interaction.response.send_message("❌ Invalid mob name")
            return

        success, message = update_setting(mob_key, enabled.lower() == "true")
        await interaction.response.send_message(message)
    
    @bot.tree.command(name="hiveslot", description = "Change the hive slot number (1-6)")
    @app_commands.describe(slot="Hive slot number (1-6, where 1 is closest to cannon)")
    async def hive_slot(interaction: discord.Interaction, slot: int):
        """Change the hive slot number"""
        try:
            # Validate slot range
            if slot < 1 or slot > 6:
                await interaction.response.send_message("❌ Hive slot must be between 1 and 6")
                return
            
            # Update the setting
            success, message = update_setting("hive_number", slot)
            
            if success:
                # Trigger GUI update if updateGUI is available
                if updateGUI is not None:
                    updateGUI.value = 1
                await interaction.response.send_message(f"✅ Hive slot changed to {slot}")
            else:
                await interaction.response.send_message(f"❌ {message}")
                
        except Exception as e:
            await interaction.response.send_message(f"❌ Error changing hive slot: {str(e)}")

    @bot.tree.command(name="usehotbar", description="Use a hotbar slot (1-7)")
    @app_commands.describe(slot="Hotbar slot number (1-7)")
    async def use_hotbar(interaction: discord.Interaction, slot: int):
        """Manually trigger a hotbar slot (updates timings and presses the key)"""
        try:
            if slot < 1 or slot > 7:
                await interaction.response.send_message("❌ Hotbar slot must be between 1 and 7")
                return

            # Determine path to src and hotbar timings file (same as macro)
            src_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            timings_path = os.path.join(src_dir, 'data', 'user', 'hotbar_timings.txt')

            # Read existing timings or initialize
            try:
                with open(timings_path, 'r') as f:
                    hotbarSlotTimings = ast.literal_eval(f.read())
            except Exception:
                hotbarSlotTimings = [0] * 8

            # Press the hotbar key twice (same behaviour as macro.backgroundOnce)
            for _ in range(2):
                keyboard.pagPress(str(slot))
                time.sleep(0.4)

            # Update the timing for this slot and save
            try:
                hotbarSlotTimings[slot] = time.time()
            except Exception:
                # If it's a dict-like structure, set the key
                hotbarSlotTimings[slot] = time.time()

            with open(timings_path, 'w') as f:
                f.write(str(hotbarSlotTimings))

            await interaction.response.send_message(f"✅ Activated hotbar slot {slot}")

        except Exception as e:
            await interaction.response.send_message(f"❌ Error using hotbar slot: {str(e)}")

    @bot.tree.command(name="macromode", description="Set macro mode (normal, quests, or field)")
    @app_commands.describe(mode="Macro mode to set")
    @app_commands.choices(mode=[
        app_commands.Choice(name="normal", value="normal"),
        app_commands.Choice(name="quests", value="quest"),
        app_commands.Choice(name="field", value="field"),
    ])
    async def macro_mode(interaction: discord.Interaction, mode: str):
        """Set macro mode"""
        try:
            success, message = update_setting("macro_mode", mode)

            # Update GUI if available
            try:
                import eel
                eel.updateMacroMode()
            except:
                pass  # GUI not available, continue

            mode_names = {
                "normal": "Normal",
                "quest": "Quest",
                "field": "Field"
            }

            await interaction.response.send_message(f"🔄 Macro mode set to {mode_names[mode]}!\n{message}")
        except Exception as e:
            await interaction.response.send_message(f"❌ Error setting macro mode: {str(e)}")

    @bot.tree.command(name="help", description="Show available commands")
    async def help_command(interaction: discord.Interaction):
        """Show available commands"""
        embed = discord.Embed(title="🤖 BSS Macro Discord Bot", description="Available Commands:", color=0x0099ff)

        embed.add_field(name="🔧 **Basic Controls**", value="`/ping` - Check if bot is online\n`/start` - Start the macro\n`/stop` - Stop the macro\n`/pause` - Pause the macro\n`/resume` - Resume the macro\n`/status` - Get macro status and current task\n`/rejoin` - Make macro rejoin game\n`/screenshot` - Get screenshot\n`/settings` - Open settings panel\n`/hiveslot <1-6>` - Change hive slot number", inline=False)

        embed.add_field(name="🌾 **Field Management**", value="`/fields` - View field configuration\n`/field <field> <true/false>` - Enable or disable a field\n`/swapfield <current> <new>` - Swap one field for another (new can be any field)", inline=False)

        embed.add_field(name="📜 **Quest Management**", value="`/quests` - View quest configuration\n`/quest <quest> <true/false>` - Enable or disable a quest", inline=False)

        embed.add_field(name="🔄 **Macro Mode**", value="`/macromode <normal/quests/field>` - Set macro mode (normal = all tasks, quests = quests only, field = fields only)", inline=False)

        embed.add_field(name="🎁 **Collectibles**", value="`/collectibles` - View collectibles\n`/collectible <item> <true/false>` - Enable or disable collectible", inline=False)

        # embed.add_field(name="🌱 **Planters**", value="`/planters` - View planter config\n`/setplantermode <mode>` - Set planter mode\n`/setmaxplanters <count>` - Set max planters", inline=False)

        embed.add_field(name="🐛 **Mob Runs**", value="`/mobs` - View mob configuration\n`/mob <mob> <true/false>` - Enable or disable mob run", inline=False)

        embed.add_field(name="📁 **Profile Management**", value="`/swapprofile <name>` - Switch to a different profile (macro must be stopped)", inline=False)

        embed.add_field(name="📊 **Status & Monitoring**", value="`/status` - Get macro status and current task\n`/tasklist` - Show enabled task order, current task, and next task\n`/logs` - Show recent macro actions\n`/battery` - Check battery status\n`/streamurl` - Get stream URL\n`/hourlyreport` - Generate and send the hourly report\n`/session` - Generate and send the final session report", inline=False)
        
        embed.add_field(name="⚙️ **Advanced**", value="`/amulet <keep/replace>` - Choose amulet action\n`/close <both/roblox/macro>` - Close both, Roblox only, or macro only", inline=False)

        await interaction.response.send_message(embed=embed)


    @bot.tree.command(name = "hourlyreport", description = "Send the hourly report")
    async def hourlyReport(interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            if HourlyReport is None or BuffDetector is None or RobloxWindowBounds is None:
                raise ImportError("Hourly report modules are not available")

            # Load settings and prepare report objects
            setdat = get_cached_settings()

            rw = RobloxWindowBounds()
            try:
                rw.setRobloxWindowBounds()
            except Exception:
                # Non-fatal: continue with default bounds
                pass

            bd = BuffDetector(rw)
            hr = HourlyReport(buffDetector=bd, time_format=setdat.get("hourly_report_time_format", 24))

            # Try loading previously saved hourly data; if missing, initialize defaults
            try:
                hr.loadHourlyReportData()
            except Exception:
                hr.hourlyReportStats = {
                    "honey_per_min": [],
                    "backpack_per_min": [],
                    "bugs": 0,
                    "quests_completed": 0,
                    "vicious_bees": 0,
                    "gathering_time": 0,
                    "converting_time": 0,
                    "bug_run_time": 0,
                    "misc_time": 0,
                    "start_time": int(time.time()),
                    "start_honey": 0,
                }
                hr.uptimeBuffsValues = {k: [0] * 600 for k in getattr(hr, "uptimeBuffsColors", {}).keys()}
                hr.buffGatherIntervals = [0] * 600

            # Generate the image (saves to hourlyReport.png)
            hr.generateHourlyReport(setdat)
            await interaction.followup.send(file = discord.File("hourlyReport.png"))

        except Exception as e:
            await interaction.followup.send(f"❌ Error generating hourly report: {str(e)}")

    @bot.tree.command(name = "session", description = "Generate and send the final session report")
    async def sessionReport(interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            if FinalReport is None:
                raise ImportError("Final report modules are not available")

            setdat = get_cached_settings()
            finalReportObj = FinalReport()
            sessionStats = finalReportObj.generateFinalReport(setdat)

            if sessionStats and os.path.exists("finalReport.png"):
                await interaction.followup.send(file=discord.File("finalReport.png"))
            else:
                await interaction.followup.send("❌ Failed to generate final session report - no data available.")

        except Exception as e:
            await interaction.followup.send(f"❌ Error generating final session report: {str(e)}")

        
    #start bot
    try:
        bot.run(token)
    except discord.errors.LoginFailure:
        print("Incorrect Bot Token", "The discord bot token you entered is invalid.")
