"""Quest objective identity, gather settings, and field scheduling."""

import re


QUEST_GIVERS = ("polar bear", "brown bear", "black bear", "honey bee", "bucko bee", "riley bee")
BLUE_FIELDS = ("blue flower", "bamboo", "pine tree", "stump")
RED_FIELDS = ("mushroom", "strawberry", "rose", "pepper")
FIELDS = ("sunflower", "dandelion", "mushroom", "blue flower", "clover", "strawberry",
          "spider", "bamboo", "pineapple", "stump", "cactus", "pumpkin", "pine tree",
          "rose", "mountain top", "pepper", "coconut")
COLOR_FIELDS = {"blue": BLUE_FIELDS, "red": RED_FIELDS,
                "white": tuple(field for field in FIELDS if field != "mountain top"), "any": FIELDS}


def quest_giver_order(settings):
    order = next((settings[key] for key in ("task_list", "task_queue", "task_priority_order")
                  if isinstance(settings.get(key), list)), [])
    ordered = [task[6:].replace("_", " ") for task in order if task.startswith("quest_")]
    return [giver for giver in dict.fromkeys(ordered + list(QUEST_GIVERS))
            if giver in QUEST_GIVERS and settings.get(giver.replace(" ", "_") + "_quest", False)]


def make_quest_objectives(giver, title, actions, statuses):
    objectives = []
    for row, (action, status) in enumerate(zip(actions, statuses)):
        kind, _, target = action.partition("_")
        field = target.replace("_", " ") if kind in ("gather", "gathergoo", "gatherpetal") else None
        color = "any"
        if kind in ("pollen", "pollengoo"):
            color = target
        elif kind == "fieldtoken":
            color = {"blueberry": "blue", "strawberry": "red"}.get(target, "any")
        elif kind == "token" and target != "honey":
            color = {"bucko bee": "blue", "riley bee": "red"}.get(giver, "any")
        objectives.append({"id": (giver, title, row), "giver": giver, "title": title,
                           "row": row, "action": action, "kind": kind, "field": field,
                           "color": color, "status": status})
    return objectives


def is_gather_objective(objective):
    return objective["kind"] in ("gather", "gathergoo", "gatherpetal", "pollen", "pollengoo", "token", "fieldtoken")


def objective_matches_text(action, text):
    """Identify a row by its requirement when some rows are missing."""
    words = set(re.findall(r"[a-z]+", text.lower()))
    kind, _, target = action.partition("_")
    if kind in ("gather", "gathergoo", "gatherpetal"):
        return set(target.replace("_", " ").split()).issubset(words)
    if kind in ("pollen", "pollengoo"):
        return target in words and ("pollen" in words or "goo" in words)
    if kind == "token":
        names = {"blueboost": ("blue", "boost"), "redboost": ("red", "boost"),
                 "blueability": ("blue", "ability"), "redability": ("red", "ability")}
        return set(names.get(target, (target,))).issubset(words)
    return False


def allowed_fields(objective, settings, field_settings):
    if objective["field"]:
        return [objective["field"]] if objective["field"] in field_settings else []
    fields = [field for field in COLOR_FIELDS.get(objective["color"], ()) if field in field_settings]
    key = objective["giver"].replace(" ", "_") + "_quest_field_" + objective["color"]
    preferred = settings.get(key, "auto")
    return [preferred] if preferred in fields else fields


def quest_gather_settings(objective, field, settings, field_settings):
    resolved = dict(field_settings[field])
    if objective["kind"] == "gatherpetal":
        resolved["shape"] = "blooms_ai"
        if settings.get("petal_quest_gather_mins", 0):
            resolved["mins"] = settings["petal_quest_gather_mins"]
        if settings.get("petal_quest_gather_return", "no override") != "no override":
            resolved["return"] = settings["petal_quest_gather_return"]
    prefix = objective["giver"].replace(" ", "_") + "_quest_gather_"
    for setting, key in (("mins", "mins"), ("return", "return"), ("pattern", "shape"), ("backpack", "backpack")):
        value = settings.get(prefix + setting, 0 if setting == "mins" else "auto")
        if value not in (None, "auto", "no override", 0, ""):
            resolved[key] = float(value) if key in ("mins", "backpack") else value
    resolved["infinite_gather"] = False
    resolved["plant_sprout"] = False
    if resolved["shape"] in ("fuzzy_ai_gather", "blooms_ai"):
        resolved["start_location"] = "center"
        resolved["shift_lock"] = False
    return resolved


def uses_quest_gumdrops(objective, settings):
    return objective["kind"] in ("gathergoo", "pollengoo") and settings.get("quest_use_gumdrops", False)


def choose_quest_gather(objectives, settings, field_settings, current_field=None):
    """Return one gather and the objectives that can share its settings."""
    order = quest_giver_order(settings)
    pending = sorted((obj for obj in objectives if is_gather_objective(obj) and obj["status"] != "complete" and obj["giver"] in order),
                     key=lambda obj: (order.index(obj["giver"]), obj["row"]))
    if not pending:
        return None
    enabled = [field for field, active in zip(settings.get("fields", []), settings.get("fields_enabled", [])) if active]
    required = [obj["field"] for obj in pending if obj["field"]]
    candidates = []
    for objective in pending:
        fields = allowed_fields(objective, settings, field_settings)
        default = "rose" if objective["color"] == "red" else "pine tree"
        preferred = next((field for field in required + enabled + [default] + fields if field in fields), None)
        for field in fields:
            resolved = quest_gather_settings(objective, field, settings, field_settings)
            gumdrops = uses_quest_gumdrops(objective, settings)
            shared = [obj for obj in pending if field in allowed_fields(obj, settings, field_settings)
                      and quest_gather_settings(obj, field, settings, field_settings) == resolved
                      and uses_quest_gumdrops(obj, settings) == gumdrops]
            candidates.append({"objective": objective, "field": field, "settings": resolved,
                               "gumdrops": gumdrops, "objectives": shared, "preferred": field == preferred})
    if not candidates:
        return None
    if settings.get("quest_scheduling", "quest giver priority") == "optimize quest completion":
        return min(candidates, key=lambda item: (item["field"] != current_field, -len(item["objectives"]),
                   order.index(item["objective"]["giver"]), item["objective"]["row"], not item["preferred"]))
    return min(candidates, key=lambda item: (order.index(item["objective"]["giver"]),
               item["objective"]["row"], not item["preferred"]))


def quest_check_due(settings, elapsed):
    return settings.get("quest_progress_check_mode", "interval") == "every iteration" or elapsed >= max(1, float(settings.get("quest_progress_check_seconds", 10)))
