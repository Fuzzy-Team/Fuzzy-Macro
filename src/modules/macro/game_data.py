"""Static Bee Swarm Simulator data used by the macro."""
import json

import cv2
import numpy as np

SPROUT_RARITIES = (
    "legendary",
    "supreme",
    "sticker",
    "gummy",
    "debug",
    "festive",
    "moon",
    "epic",
    "rare",
    "common",
)
SPROUT_REPLANT_FALLBACK_SECONDS = {
    "common": 15,
    "rare": 30,
    "moon": 45,
    "epic": 60,
    "gummy": 75,
    "festive": 75,
    "legendary": 90,
    "supreme": 120,
    "sticker": 120,
    "debug": 120,
}
STICKER_SPROUT_SPAWN_MINUTE_OF_DAY = (2 * 60) + 30
STICKER_SPROUT_INTERVAL_SECONDS = 3 * 60 * 60
STICKER_SPROUT_COLLECTION_WINDOW_SECONDS = 12 * 60

#data for collectable objectives
#[besideE text, movement key, max cooldowns]
collectData = { 
    "wealth_clock": [["use"], "w", 1*60*60], #1hr
    "honey_dispenser": [["use", "honey"], None, 1*60*60], #1hr
    "blueberry_dispenser": [["use", "dispenser"], "a", 4*60*60], #4hr
    "strawberry_dispenser": [["use", "dispenser"], None, 4*60*60], #4hr
    "coconut_dispenser": [["use", "dispenser"], "s", 4*60*60], #4hr
    "royal_jelly_dispenser": [["claim", "royal"], "a",22*60*60], #22hr
    "treat_dispenser": [["use", "treat"], "w", 1*60*60], #1hr
    "ant_pass_dispenser": [["use", "free"], "w", 2*60*60], #2hr
    # "Spend 10 Tickets to Use the Ant Pass Dispenser" — same inventory cap as free
    "buy_ant_pass": [["spend", "ticket"], "w", 0],
    "robo_pass_dispenser": [["use", "free", "robo", "pass", "passes"], None, 22*60*60], #22hr
    "glue_dispenser": [["use", "glue"], None, 22*60*60], #22hr
    "stockings": [["check", "inside", "stocking"], "a", 1*60*60], #1hr
    "wreath": [["admire", "honey"], "a", 30*60], #30mins
    "feast": [["dig", "beesmas"], "s", 1.5*60*60], #1.5hr
    "gingerbread": [["gingerbread", "inside", "check"], None, 2*60*60], #2hr
    "samovar": [["heat", "samovar", "strange"], "w", 6*60*60], #6hr
    "snow_machine": [["activ", "machine"], None, 2*60*60], #2hr
    "lid_art": [["gander", "onett", "art"], "s", 8*60*60], #8hr
    "candles": [["admire", "candle", "honey"], "w", 4*60*60], #4hr
    "gummy_beacon": [["gummy", "beacon", "siege", "satellite", "satelite", "vibes", "progress"], None, 8*60*60], #8hr
    "memory_match": [["spend", "play"], "a", 2*60*60], #2hr
    "mega_memory_match": [["spend", "play"], "w", 4*60*60], #4hr
    "extreme_memory_match": [["spend", "play"], "w", 8*60*60], #8hr
    "winter_memory_match": [["spend", "play"], "a", 4*60*60], #4hr
    "honeystorm": [["sum", "honey", "mmon", "storm"], "s", 4*60*60], #4hr
    "wind_shrine": [["inspect", "wind", "shrine"], None, 1*60*60], #1hr
}

#these collects are added seperately as they need to be handled seperately instead of being iterated through by the main loop
fieldBoosterData = {
    "blue_booster": [["use", "booster"], "w", 45*60], #45mins
    "red_booster": [["use", "booster"], "s", 45*60], #45mins
    "mountain_booster": [["use", "booster"], None, 45*60], #45mins
}

mergedCollectData = {**collectData, **fieldBoosterData}
mergedCollectData["sticker_stack"] = [["add", "sticker"], None, 0]
mergedCollectData["sticker_sprout"] = [["sticker", "sprout"], None, 3*60*60]

windShrineDonationItems = [
    "ticket", "tickets",
    "gumdrops",
    "coconut", "coconuts",
    "stinger", "stingers",
    "micro-converter", "micro-converters", "micro converter", "micro converters",
    "honeysuckle", "honeysuckles",
    "whirligig", "whirligigs",
    "field dice",
    "smooth dice",
    "loaded dice",
    "jelly beans",
    "red extract", "red extracts",
    "blue extract", "blue extracts",
    "glitter",
    "glue", "glues",
    "oil", "oils",
    "enzymes",
    "tropical drink", "tropical drinks",
    "purple potion", "purple potions",
    "marshmallow bee", "marshmallow bees",
    "magic bean", "magic beans",
    "festive bean", "festive beans",
    "cloud vial", "cloud vials",
    "night bell", "night bells",
    "box-o-frogs", "boxes-o-frogs", "box o frogs", "boxes o frogs",
    "ant pass", "ant passes",
    "treat", "treats",
    "atomic treat", "atomic treats",
    "star treat", "star treats",
    "sunflower seed", "sunflower seeds",
    "strawberry", "strawberries",
    "pineapple", "pineapples",
    "blueberry", "blueberries",
    "bitterberry", "bitterberries",
    "neonberry", "neonberries",
    "moon charm", "moon charms",
    "soft wax", "soft waxes",
    "hard wax", "hard waxes",
    "caustic wax", "caustic waxes",
    "swirled wax", "swirled waxes",
    "turpentine", "turpentines",
    "basic egg", "basic eggs", "honey bee egg",
    "silver egg", "silver eggs",
    "gold egg", "gold eggs",
    "diamond egg", "diamond eggs",
    "mythic egg", "mythic eggs",
    "star egg", "star eggs",
    "gifted silver egg", "gifted silver eggs",
    "gifted gold egg", "gifted gold eggs",
    "gifted diamond egg", "gifted diamond eggs",
    "gifted mythic egg", "gifted mythic eggs",
    "royal jelly", "royal jellies",
    "star jelly", "star jellies",
]

#werewolf is a unique one. There is only one, but it can be triggered from pine, pumpkin or cactus
regularMobQuantitiesInFields = {
    "rose": {
        "scorpion": 2
    },
    "pumpkin": {
        "werewolf": 1
    },
    "cactus": {
        "werewolf": 1
    },
    "spider": {
        "spider": 1
    },
    "clover": {
        "ladybug": 1,
        "rhinobeetle": 1
    },
    "strawberry": {
        "ladybug": 2,
    },
    "bamboo": {
        "rhinobeetle": 2
    },
    "mushroom": {
        "ladybug": 1
    },
    "blue flower": {
        "rhinobeetle": 1
    },
    "pineapple": {
        "mantis": 1,
        "rhinobeetle": 1
    },
    "pine tree": {
        "mantis": 2,
        "werewolf": 1
    },
}
regularMobTypesInFields = {k: [x[0] for x in v] for k, v in {k:list(v.items()) for k,v in regularMobQuantitiesInFields.items()}.items()}

mobRespawnTimes = {
    "ladybug": 5*60, #5mins
    "rhinobeetle": 5*60, #5mins
    "spider": 30*60, #30mins
    "mantis": 20*60, #20mins
    "scorpion": 20*60, #20mins
    "werewolf": 60*60 #1hr
}

# Define the color range for reset detection (in HSL color space)
#white color respawn pad
resetLower1 = np.array([0, 102, 0])  # Lower bound of the color (H, L, S)
resetUpper1 = np.array([40, 255, 30])  # Upper bound of the color (H, L, S)
#balloon color
resetLower2 = np.array([105, 140, 210])  # Lower bound of the color (H, L, S)
resetUpper2 = np.array([120, 220, 255])  # Upper bound of the color (H, L, S)
resetKernel = cv2.getStructuringElement(cv2.MORPH_RECT,(16,10))


#store planter's growth data
#[growth time in secs, (list of bonus fields), bonus growth from fields]
planterGrowthData = {
    "paper": [1*60*60, (), 0], #1hr
    "ticket": [2*60*60, (), 0], #2hr
    "festive": [4*60*60, (), 0], #4hr
    "sticker": [3*60*60, (), 0], #3hr
    "plastic": [2*60*60, (), 0], #2hr
    "candy": [4*60*60, ("strawberry", "pineapple", "coconut"), 0.25], #4hr
    "red clay": [6*60*60, ("sunflower", "dandelion", "mushroom", "clover", "strawberry", "pineapple", "stump", "cactus", "pumpkin", "rose", "mountain top", "pepper", "coconut"), 0.25], #6hr
    "blue clay": [6*60*60, ("sunflower", "dandelion", "blue flower", "clover", "bamboo", "pineapple", "stump", "cactus", "pumpkin", "pine tree", "mountain top", "coconut"), 0.25], #6hr
    "tacky": [8*60*60, ("sunflower", "dandelion", "mushroom", "blue flower", "clover"), 0.25], #8hr
    "pesticide": [10*60*60, ("bamboo", "spider", "strawberry"), 0.3], #10hr
    "heat-treated": [12*60*60, ("sunflower", "dandelion", "mushroom", "clover", "strawberry", "pineapple", "stump", "cactus", "pumpkin", "rose", "mountain top", "pepper", "coconut"), 0.5], #12hr
    "hydroponic": [12*60*60, ("sunflower", "dandelion", "blue flower", "clover", "bamboo", "pineapple", "stump", "cactus", "pumpkin", "pine tree", "mountain top", "coconut"), 0.5], #12hr
    "petal": [14*60*60, ("sunflower", "dandelion", "blue flower", "mushroom" "clover", "bamboo", "strawberry", "pineapple", "stump", "cactus", "pumpkin", "pine tree", "rose", "mountain top", "coconut", "pepper"), 0.5], #14hrs
    "planter of plenty": [16*60*60, ("pepper", "stump", "coconut", "mountain top"), 0.5] #16hr
}

#a list of all items that can be crafted by the blender in order
BLENDER_ITEM_SLOTS = 5
blenderItems = ["red extract", "blue extract", "enzymes", "oil", "glue", "tropical drink", "gumdrops", "moon charm",
    "glitter",
    "star jelly",
    "purple potion",
    "soft wax",
    "hard wax",
    "swirled wax",
    "caustic wax",
    "field dice",
    "smooth dice",
    "loaded dice",
    "super smoothie",
    "turpentine"]

MAIN_GAME_PLACE_ID = "1537690962"
HIVE_HUB_PLACE_ID = "15579077077"
# share of the Roblox window that must match one sample color to count as the rejoin/loading screen
REJOIN_COLOR_PERCENT = 0.7754


SPROUT_FIELD_TOKEN_PRIORITY = {
    "sunflower": ["Sunflower Seed"],
    "pineapple": ["Pineapple"],
    "strawberry": ["Strawberry"],
    "coconut": ["Coconut"],
    "blue flower": ["Blueberry"],
    "bamboo": ["Blueberry"],
    "pine tree": ["Blueberry"],
    "stump": ["Blueberry"],
    "mushroom": ["Strawberry"],
    "rose": ["Strawberry"],
    "pepper": ["Strawberry"],
}

SPROUT_BASE_TOKEN_PRIORITY = [
    "Token Link",
    "Coconut",
    "Pineapple",
    "Blueberry",
    "Strawberry",
    "Sunflower Seed",
    "Jelly Bean",
    "Snowflake",
    "Beesmas Cheer Token",
    "Festive Blessing Token",
    "Treat",
    "Honey Token",
]

#a list of keys to press to face north after running the cannon_to_field path

fieldFaceNorthKeys = {
    "sunflower": ["."]*2,
    "dandelion": [","]*2,
    "mushroom": None,
    "blue flower": [","]*2,
    "clover": ["."]*4,
    "strawberry": ["."]*2,
    "spider": None,
    "bamboo": [","]*2,
    "pineapple": None,
    "stump": [","]*2,
    "cactus": ["."]*4,
    "pumpkin": None,
    "pine tree": None,
    "rose": ["."]*2,
    "mountain top": ["."]*4,
    "pepper": ["."]*2,
    "coconut": ["."]*4,
    "hive hub": None
}

#the field dimensions taken from natro
#[length, width]
startLocationDimensions = {
    "sunflower": [1250, 2000],
    "dandelion": [2500, 1000],
    "mushroom": [1250, 1750],
    "blue flower": [2750, 750],
    "clover": [2000, 1500],
    "strawberry": [1500, 2000],
    "spider": [2000, 2000],
    "bamboo": [3000, 1250],
    "pineapple": [1750, 3000],
    "stump": [1500, 1500],
    "cactus": [1500, 2500],
    "pumpkin": [1500, 2500],
    "pine tree": [2500, 1700],
    "rose": [2500, 1500],
    "mountain top": [2250, 1500],
    "pepper": [1500, 2250],
    "coconut": [1500, 2250],
    "hive hub": [0, 0]
}

hiveHubStartLocationOffsets = {
    "center": [],
    "right": [("d", 2)],
    "left": [("a", 2)],
    "top": [("w", 2)],
    "bottom": [("s", 2)],
    "upper right": [("w", 2), ("d", 2)],
    "lower right": [("s", 2), ("d", 2)],
    "upper left": [("a", 2), ("w", 2)],
    "lower left": [("a", 2), ("s", 2)],
}

#for the ocr
#sometimes, it reads the bss font as crillic characters, so it'll need to be converted back to latin
#This isn't an actual translation, the characters are mapped visually
cyrillicToLatin = {
    'А': 'A', 
    'В': 'B', 
    'Е': 'E', 
    'К': 'K', 
    'М': 'M', 
    'Н': 'H',
    'О': 'O', 
    'Р': 'P', 
    'С': 'C', 
    'Т': 'T', 
    'У': 'Y', 
    'Х': 'X',
    'а': 'a', 
    'в': 'B', 
    'е': 'e', 
    'к': 'k', 
    'м': 'm', 
    'н': 'h',
    'о': 'o', 
    'р': 'p', 
    'с': 'c', 
    'т': 't', 
    'у': 'y', 
    'х': 'x'
}

def _loadQuestData(path="./data/bss/quest_data.txt"):
    """Parse quest_data.txt into {bear: {quest title: [objectives]}}."""
    questData = {}
    bear, title, objectives = "", "", []
    with open(path, "r") as f:
        for line in (x for x in f.read().split("\n") if x):
            if line.startswith("==") and line.endswith("=="):
                if title:
                    questData[bear][title] = objectives
                bear = line.strip("=")
                questData[bear] = {}
                title, objectives = "", []
            elif line.startswith("-"):
                if title:
                    questData[bear][title] = objectives
                title = line.lstrip("-").strip()
                objectives = []
            else:
                objectives.append(line)
    questData[bear][title] = objectives
    return questData


quest_data = _loadQuestData()

#planter-related info
nectarNames=["comforting", "refreshing", "satisfying", "motivating", "invigorating"]
nectarFields = {
  "comforting": ["dandelion", "bamboo", "pine tree"],
  "refreshing": ["coconut", "strawberry", "blue flower"],
  "satisfying": ["pineapple", "sunflower", "pumpkin"],
  "motivating": ["stump", "spider", "mushroom", "rose"],
  "invigorating": ["pepper", "mountain top", "clover", "cactus"]
}
allPlanters = ["paper", "ticket", "festive", "sticker", "plastic", "candy", "red_clay", "blue_clay", "tacky", "pesticide", "heat-treated", "hydroponic", "petal", "planter_of_plenty"]
with open("./data/bss/auto_planter_ranking.json", "r") as f:
    autoPlanterRankings = json.load(f)


# Quest completer name mappings
questCompleterFieldNames = {
    # Common field name variations
    "strawberry": "strawberry",
    "strawberries": "strawberry",
    "blue_flower": "blue flower",
    "blue flower": "blue flower",
    "blueflower": "blue flower",
    "pine_tree": "pine tree",
    "pine tree": "pine tree",
    "pinetree": "pine tree",
    "sunflower": "sunflower",
    "sunflowers": "sunflower",
    "mushroom": "mushroom",
    "mushrooms": "mushroom",
    "rose": "rose",
    "roses": "rose",
    "clover": "clover",
    "clovers": "clover",
    "bamboo": "bamboo",
    "cactus": "cactus",
    "cactuses": "cactus",
    "pumpkin": "pumpkin",
    "pumpkins": "pumpkin",
    "pineapple": "pineapple",
    "pineapples": "pineapple",
    "coconut": "coconut",
    "coconuts": "coconut",
    "dandelion": "dandelion",
    "dandelions": "dandelion",
    "spider": "spider",
    "spiders": "spider",
    "stump": "stump",
    "stumps": "stump",
    "pepper": "pepper",
    "peppers": "pepper",
    "mountain_top": "mountain top",
    "mountain top": "mountain top",
    "mountaintop": "mountain top"
}

questCompleterMobNames = {
    # Common mob name variations
    "scorpion": "scorpion",
    "scorpions": "scorpion",
    "mantis": "mantis",
    "mantises": "mantis",
    "spider": "spider",
    "spiders": "spider",
    "ladybug": "ladybug",
    "ladybugs": "ladybug",
    "rhinobeetle": "rhinobeetle",
    "rhino_beetle": "rhinobeetle",
    "rhino beetle": "rhinobeetle",
    "rhinobeetles": "rhinobeetle",
    "ant": "ant",
    "ants": "ant",
    "giant_ant": "ant",
    "giant ant": "ant",
    "giant_ants": "ant",
    "giant ants": "ant",
    "army_ant": "ant",
    "army ant": "ant",
    "armyant": "ant",
    "army_ants": "ant",
    "army ants": "ant",
    "fire_ant": "ant",
    "fire ant": "ant",
    "fireant": "ant",
    "fire_ants": "ant",
    "fire ants": "ant",
    "werewolf": "werewolf",
    "werewolves": "werewolf",
    "wolf": "werewolf",
    "wolves": "werewolf",
    "king_beetle": "king_beetle",
    "king beetle": "king_beetle",
    "tunnel_bear": "tunnel_bear",
    "tunnel bear": "tunnel_bear",
    "coconut_crab": "coconut_crab",
    "coconut crab": "coconut_crab",
    "coconut_crabs": "coconut_crab",
    "coconut crabs": "coconut_crab",
    "coconutcrab": "coconut_crab",
    "coconutcrabs": "coconut_crab",
    "mechsquito": "mechsquito",
    "mechsquitos": "mechsquito"
}

questCompleterCollectNames = {
    # Common collectible name variations
    "blue_booster": "blue_booster",
    "blue booster": "blue_booster",
    "red_booster": "red_booster",
    "red booster": "red_booster",
    "mountain_booster": "mountain_booster",
    "mountain booster": "mountain_booster",
    "sticker_printer": "sticker_printer",
    "sticker printer": "sticker_printer",
    "sticker_stack": "sticker_stack",
    "sticker stack": "sticker_stack",
    "blueberry_dispenser": "blueberry_dispenser",
    "blueberry dispenser": "blueberry_dispenser",
    "strawberry_dispenser": "strawberry_dispenser",
    "strawberry dispenser": "strawberry_dispenser",
    "coconut_dispenser": "coconut_dispenser",
    "coconut dispenser": "coconut_dispenser",
    "royal_jelly_dispenser": "royal_jelly_dispenser",
    "royal jelly dispenser": "royal_jelly_dispenser",
    "treat_dispenser": "treat_dispenser",
    "treat dispenser": "treat_dispenser",
    "ant_pass_dispenser": "ant_pass_dispenser",
    "ant pass dispenser": "ant_pass_dispenser",
    "buy_ant_pass": "buy_ant_pass",
    "buy ant pass": "buy_ant_pass",
    "glue_dispenser": "glue_dispenser",
    "glue dispenser": "glue_dispenser",
    "wealth_clock": "wealth_clock",
    "wealth clock": "wealth_clock",
    "stockings": "stockings",
    "wreath": "wreath",
    "feast": "feast",
    "samovar": "samovar",
    "snow_machine": "snow_machine",
    "snow machine": "snow_machine",
    "lid_art": "lid_art",
    "lid art": "lid_art",
    "candles": "candles",
    "memory_match": "memory_match",
    "memory match": "memory_match",
    "mega_memory_match": "mega_memory_match",
    "mega memory match": "mega_memory_match",
    "extreme_memory_match": "extreme_memory_match",
    "extreme memory match": "extreme_memory_match",
    "winter_memory_match": "winter_memory_match",
    "winter memory match": "winter_memory_match",
    "honeystorm": "honeystorm",
    "honey_storm": "honeystorm",
    "honey storm": "honeystorm",
    "honey_dispenser": "honey_dispenser",
    "honey dispenser": "honey_dispenser",
    "robo_pass_dispenser": "robo_pass_dispenser",
    "robo pass dispenser": "robo_pass_dispenser",
    "robo pass": "robo_pass_dispenser",
    "gummy_beacon": "gummy_beacon",
    "gummy beacon": "gummy_beacon",
    "gingerbread": "gingerbread",
    "gingerbread house": "gingerbread",
    "wind_shrine": "wind_shrine",
    "wind shrine": "wind_shrine"
} 

PING_SETTING_KEYS = [
    "ping_critical_errors",
    "ping_disconnects",
    "ping_character_deaths",
    "ping_vicious_bee",
    "ping_mondo_buff",
    "ping_ant_challenge",
    "ping_sticker_events",
    "ping_mob_events",
    "ping_conversion_events",
    "ping_hourly_reports",
    "ping_guiding_star",
    "ping_unusual_sprouts",
    "ping_windy_bee",
    "ping_macro_status",
    "ping_gathering",
    "ping_live_gather_report",
    "ping_final_reports",
    "ping_planters",
    "ping_collectibles",
    "ping_quests",
    "ping_boosts",
    "ping_crafting",
    "ping_stream",
]
