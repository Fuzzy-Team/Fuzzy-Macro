"""Quest objective identity, gather settings, and field scheduling."""

import re
from pathlib import Path


QUEST_GIVERS = ("polar bear", "brown bear", "black bear", "honey bee", "bucko bee", "riley bee",
                "panda bear", "science bear", "mother bear", "onett", "spirit bear")
# Givers with a fixed list of quests that ends: they are switched off after the last one.
FIXED_LINE_GIVERS = ("panda bear", "science bear", "mother bear", "onett", "spirit bear")
# Hive bees needed before a giver talks to you; givers above the config's bee count stay locked.
QUEST_GIVER_MIN_BEES = {"panda bear": 5, "science bear": 10, "onett": 30, "spirit bear": 35}
# Items quest rows can use: key -> (inventory name, setting that allows it, when the macro uses it).
# "gather" and "convert" uses ride along with a gather/conversion; "hub" is its own trip.
QUEST_ITEMS = {
    "jellybean": ("jelly beans", "quest_use_jelly_beans", "hub"),
    "magicbean": ("magic bean", "quest_use_magic_beans", "gather"),
    "cloudvial": ("cloud vial", "quest_use_cloud_vials", "gather"),
    "redextract": ("red extract", "quest_use_extracts", "gather"),
    "blueextract": ("blue extract", "quest_use_extracts", "gather"),
    "fielddice": ("field dice", "quest_use_field_dice", "convert"),
}
# Row kinds that need a setting before the macro will spend items or tickets on them.
QUEST_DONATE_SETTING = "quest_donate_wind_shrine"
QUEST_PAIRS_SETTING = "quest_play_memory_match"
BLUE_FIELDS = ("blue flower", "bamboo", "pine tree", "stump")
RED_FIELDS = ("mushroom", "strawberry", "rose", "pepper")
FIELDS = ("sunflower", "dandelion", "mushroom", "blue flower", "clover", "strawberry",
          "spider", "bamboo", "pineapple", "stump", "cactus", "pumpkin", "pine tree",
          "rose", "mountain top", "pepper", "coconut")
COLOR_FIELDS = {"blue": BLUE_FIELDS, "red": RED_FIELDS,
                "white": tuple(field for field in FIELDS if field != "mountain top"), "any": FIELDS}
# Quest-only gather settings per objective: allowed values besides "auto", which keeps the field's value.
OBJECTIVE_SETTING_CHOICES = {
    "size": ("xs", "s", "m", "l", "xl"),
    "width": tuple(str(number) for number in range(1, 9)),
    "invert_lr": ("on", "off"),
    "invert_fb": ("on", "off"),
    "shift_lock": ("on", "off"),
    "field_drift_compensation": ("on", "off"),
    "turn": ("none", "left", "right"),
    "turn_times": ("1", "2", "3", "4"),
    "use_whirlwig_fallback": ("on", "off"),
    "start_location": ("center", "upper right", "right", "lower right", "bottom",
                       "lower left", "left", "upper left", "top"),
    "distance": tuple(str(number) for number in range(1, 11)),
    "goo": ("on", "off"),
    "goo_interval": ("3", "5", "10", "15", "30", "60"),
}
QUEST_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "bss" / "quest_data.txt"


def load_quest_catalog(path=QUEST_DATA_PATH):
    """Read the shared quest catalog used by detection and the settings editor."""
    catalog = {}
    giver, title = None, None
    with open(path, encoding="utf-8") as source:
        for line in (line.strip() for line in source):
            if not line:
                continue
            if line.startswith("==") and line.endswith("=="):
                giver, title = line.strip("="), None
                catalog[giver] = {}
            elif line.startswith("-"):
                title = line.lstrip("-").strip()
                catalog[giver][title] = []
            else:
                catalog[giver][title].append(line)
    return catalog


def objective_type(action):
    return re.sub(r"^(kill|feed|use|donate)_(?:\d+|\*)_", r"\1_", action.replace(" ", "_"))


def objective_setting_prefix(objective):
    return "quest_objective_" + objective_type(objective["action"]) + "_"


def gather_objective_types(catalog):
    """Describe each catalog gathering objective once, independent of giver."""
    types = {}
    for quests in catalog.values():
        for actions in quests.values():
            for objective in make_quest_objectives("", "", actions, ["unknown"] * len(actions)):
                if not is_gather_objective(objective):
                    continue
                key = objective_type(objective["action"])
                kind, _, target = objective["action"].partition("_")
                name = target.replace("_", " ").title()
                if kind == "use":
                    label = "Use " + QUEST_ITEMS[target.partition("_")[2]][0].title()
                elif kind in ("gather", "gathergoo", "gatherpetal"):
                    label = {"gather": "Pollen", "gathergoo": "Goo", "gatherpetal": "Bloom Petals"}[kind] + " in " + name
                elif kind in ("pollen", "pollengoo"):
                    label = "Collect " + name + (" Pollen" if kind == "pollen" else " Goo")
                else:
                    name = {"redability": "Red Ability", "blueability": "Blue Ability",
                            "redboost": "Red Boost", "blueboost": "Blue Boost"}.get(target, name)
                    label = "Collect " + name + " Tokens"
                types[key] = {"value": key, "label": label, "field": objective["field"],
                              "fields": [objective["field"]] if objective["field"] else list(COLOR_FIELDS[objective["color"]])}
    return [types[key] for key in sorted(types)]


def quest_giver_order(settings):
    order = next((settings[key] for key in ("task_list", "task_queue", "task_priority_order")
                  if isinstance(settings.get(key), list)), [])
    ordered = [task[6:].replace("_", " ") for task in order if task.startswith("quest_")]
    return [giver for giver in dict.fromkeys(ordered + list(QUEST_GIVERS))
            if giver in QUEST_GIVERS and settings.get(giver.replace(" ", "_") + "_quest", False)
            and settings.get("bees", 50) >= QUEST_GIVER_MIN_BEES.get(giver, 0)]


def manual_objective_name(action):
    """'manual_use 10 red portal' -> 'Use 10 Red Portal'; 'use_10_fielddice' -> 'Use 10 Field Dice'"""
    kind, _, target = action.partition("_")
    if kind == "use":
        count, _, key = target.partition("_")
        return f"Use {count} {QUEST_ITEMS[key][0].title()}"
    if kind == "donate":
        count, _, item = target.partition("_")
        return f"Donate {count} {item.title()} to the Wind Shrine"
    if kind == "pairs":
        return f"Match {target} Memory Match pairs"
    return target.title()


def quest_item(objective):
    """Inventory key of a use row: 'use_10_fielddice' -> 'fielddice'."""
    return objective["action"].rpartition("_")[2] if objective["kind"] == "use" else None


def objective_allowed(objective, settings):
    """False for rows the user keeps to themselves: manual rows, and item/ticket rows whose setting is off."""
    kind = objective["kind"]
    if kind == "use":
        return bool(settings.get(QUEST_ITEMS[quest_item(objective)][1]))
    if kind == "donate":
        return bool(settings.get(QUEST_DONATE_SETTING))
    if kind == "pairs":
        return bool(settings.get(QUEST_PAIRS_SETTING))
    return kind != "manual"


def make_quest_objectives(giver, title, actions, statuses, remaining=None):
    """remaining: what the quest log still asks for per row (None where it couldn't be read)."""
    objectives = []
    identity_title = tuple(actions) if giver == "brown bear" else title
    for row, (action, status) in enumerate(zip(actions, statuses)):
        kind, _, target = action.partition("_")
        field = target.replace("_", " ") if kind in ("gather", "gathergoo", "gatherpetal") else None
        color = "any"
        if kind in ("pollen", "pollengoo"):
            color = target
        elif kind == "fieldtoken":
            color = {"blueberry": "blue", "strawberry": "red"}.get(target, "any")
        elif kind == "token" and target != "honey":
            color = {"blueability": "blue", "blueboost": "blue", "bomb": "blue",
                     "redability": "red", "redboost": "red", "rage": "red"}.get(target, "any")
        objectives.append({"id": (giver, identity_title, row), "giver": giver, "title": title,
                           "row": row, "action": action, "kind": kind, "field": field,
                           "color": color, "status": status,
                           "remaining": remaining[row] if remaining else None})
    return objectives


def quest_uses_ant_challenge(action, settings):
    return action == "challenge_ant" or (
        action == "token_rage" and settings.get("quest_objective_token_rage_field", "auto") == "auto")


def is_gather_objective(objective, settings=None):
    if objective["kind"] == "use":
        # Items used during a gather or conversion need that trip made; the hub trip stands alone.
        return (QUEST_ITEMS[quest_item(objective)][2] != "hub"
                and (settings is None or objective_allowed(objective, settings)))
    return (objective["kind"] in ("gather", "gathergoo", "gatherpetal", "pollen", "pollengoo", "token", "fieldtoken")
            and (settings is None or not quest_uses_ant_challenge(objective["action"], settings)))


def objective_matches_text(action, text):
    """Identify a row by its requirement when some rows are missing."""
    def singular(word):
        if word in ("werewolves", "mantises"):
            return {"werewolves": "werewolf", "mantises": "mantis"}[word]
        word = re.sub(r"ies$", "y", word)
        return word[:-1] if word.endswith("s") and word != "mantis" else word

    tokens = [singular(word) for word in re.findall(r"[a-z]+", text.lower())]
    words = set(tokens)
    kind, _, target = action.partition("_")
    if kind in ("gather", "gathergoo", "gatherpetal"):
        return {singular(word) for word in target.replace("_", " ").split()}.issubset(words)
    if kind in ("pollen", "pollengoo"):
        if target == "any":
            # Any-colour pollen names no colour or field; otherwise every gather row would match it.
            return ("pollen" if kind == "pollen" else "goo") in words and not words.intersection(("white", "blue", "red", "field", "from"))
        return target in words and ("pollen" in words or "goo" in words)
    if kind == "token":
        names = {"blueboost": ("blue", "boost"), "redboost": ("red", "boost"),
                 "blueability": ("blue", "ability"), "redability": ("red", "ability")}
        return set(names.get(target, (target,))).issubset(words)
    if kind == "kill":
        target = re.sub(r"^\d+_", "", target)
        name = "".join(singular(word) for word in re.findall(r"[a-z]+", target))
        nouns = {"".join(tokens[index:index + length]) for index in range(len(tokens)) for length in (1, 2)}
        return name in nouns and bool(words.intersection(("defeat", "kill", "slay", "destroy")))
    if kind == "feed":
        item = target.split("_", 1)[-1]
        return {singular(word) for word in item.replace("_", " ").split()}.issubset(words) and bool(words.intersection(("feed", "give")))
    if kind == "collect":
        return set(re.findall(r"[a-z]+", target)).issubset(words)
    if kind == "fieldtoken":
        return target in words and bool(words.intersection(("collect", "token")))
    if kind in ("use", "donate"):
        item = QUEST_ITEMS[target.rpartition("_")[2]][0] if kind == "use" else target.partition("_")[2]
        verbs = ("use", "share") if kind == "use" else ("donate",)
        return {singular(word) for word in item.split()}.issubset(words) and bool(words.intersection(verbs))
    if kind == "pairs":
        return "pair" in words
    return False


def allowed_fields(objective, settings, field_settings):
    if objective["field"]:
        return [objective["field"]] if objective["field"] in field_settings else []
    fields = [field for field in COLOR_FIELDS.get(objective["color"], ()) if field in field_settings]
    key = objective_setting_prefix(objective) + "field"
    preferred = settings.get(key, "auto")
    return [preferred] if preferred in fields else fields


def quest_gather_settings(objective, field, settings, field_settings):
    resolved = dict(field_settings[field])
    if objective["kind"] in ("gathergoo", "pollengoo"):
        resolved["goo"] = True
        resolved["goo_interval"] = 3
    if objective["kind"] == "gatherpetal":
        resolved["shape"] = "blooms_ai"
        if settings.get("petal_quest_gather_mins", 0):
            resolved["mins"] = settings["petal_quest_gather_mins"]
        if settings.get("petal_quest_gather_return", "no override") != "no override":
            resolved["return"] = settings["petal_quest_gather_return"]
    prefix = objective_setting_prefix(objective)
    for setting, key in (("mins", "mins"), ("return", "return"), ("pattern", "shape"), ("backpack", "backpack")):
        value = settings.get(prefix + setting, 0 if setting == "mins" else "auto")
        if value not in (None, "auto", "no override", 0, ""):
            resolved[key] = float(value) if key in ("mins", "backpack") else value
    for setting in OBJECTIVE_SETTING_CHOICES:
        value = str(settings.get(prefix + setting, "auto"))
        if value in ("on", "off"):
            resolved[setting] = value == "on"
        elif value != "auto":
            resolved[setting] = int(value) if value.isdigit() else value
    resolved["infinite_gather"] = False
    resolved["plant_sprout"] = False
    if resolved["shape"] in ("fuzzy_ai_gather", "blooms_ai"):
        resolved["start_location"] = "center"
        resolved["shift_lock"] = False
    return resolved


def preferred_quest_field(objective, settings, field_settings, required=()):
    fields = allowed_fields(objective, settings, field_settings)
    enabled = [field for field, active in zip(settings.get("fields", []), settings.get("fields_enabled", [])) if active]
    default = "rose" if objective["color"] == "red" else "pine tree"
    return next((field for field in list(required) + enabled + [default] + fields if field in fields), None)


def quest_gather_defaults(action, settings, field_settings):
    """Preview each Auto choice using the same field and setting rules as gathering."""
    objective = make_quest_objectives("", "", [action], ["unknown"])[0]
    prefix = objective_setting_prefix(objective)
    field = preferred_quest_field(objective, settings, field_settings)
    defaults = {"field": preferred_quest_field(objective, {**settings, prefix + "field": "auto"}, field_settings)}
    if action == "token_rage":
        defaults["field"] = "ant challenge"
    properties = {"pattern": "shape", "mins": "mins", "backpack": "backpack", "return": "return",
                  **{key: key for key in OBJECTIVE_SETTING_CHOICES}}
    for property_name, key in properties.items():
        inherited = {**settings, prefix + property_name: "auto"}
        defaults[property_name] = quest_gather_settings(objective, field, inherited, field_settings)[key]
    return defaults


def choose_quest_gather(objectives, settings, field_settings, current_field=None):
    """Return one gather and the objectives that can share its settings."""
    order = quest_giver_order(settings)
    pending = sorted((obj for obj in objectives if is_gather_objective(obj, settings) and obj["status"] != "complete" and obj["giver"] in order),
                     key=lambda obj: (order.index(obj["giver"]), obj["row"]))
    if not pending:
        return None
    required = [fields[0] for obj in pending
                if len(fields := allowed_fields(obj, settings, field_settings)) == 1]
    candidates = []
    for objective in pending:
        fields = allowed_fields(objective, settings, field_settings)
        preferred = preferred_quest_field(objective, settings, field_settings, required)
        for field in fields:
            resolved = quest_gather_settings(objective, field, settings, field_settings)
            shared = [obj for obj in pending if field in allowed_fields(obj, settings, field_settings)
                      and quest_gather_settings(obj, field, settings, field_settings) == resolved]
            candidates.append({"objective": objective, "field": field, "settings": resolved,
                               "objectives": shared, "preferred": field == preferred})
    if not candidates:
        return None
    if settings.get("quest_scheduling", "quest giver priority") == "optimize quest completion":
        return min(candidates, key=lambda item: (item["field"] != current_field, -len(item["objectives"]),
                   order.index(item["objective"]["giver"]), item["objective"]["row"], not item["preferred"]))
    return min(candidates, key=lambda item: (order.index(item["objective"]["giver"]),
               item["objective"]["row"], not item["preferred"]))


def quest_check_due(settings, elapsed):
    return settings.get("quest_progress_check_mode", "interval") == "every iteration" or elapsed >= max(1, float(settings.get("quest_progress_check_seconds", 10)))
