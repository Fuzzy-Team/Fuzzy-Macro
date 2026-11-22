"""Field, goo and honey badges the macro can progress by gathering.

Quest, battle, ability, playtime and sticker badges can't be earned by gathering, so they are left out.
"""

# Badge titles in the badge menu read "<name> Badge".
FIELD_BADGES = {
    "sunflower": "Sunflower", "dandelion": "Dandelion", "mushroom": "Mushroom", "blue flower": "Blue Flower",
    "clover": "Clover", "spider": "Spider", "strawberry": "Strawberry", "bamboo": "Bamboo",
    "pineapple": "Pineapple", "pumpkin": "Pumpkin", "cactus": "Cactus", "rose": "Rose",
    "pine tree": "Pine Tree", "stump": "Stump", "coconut": "Coconut", "pepper": "Pepper",
    "hive hub": "Hive Hub", "mountain top": "Mountain Top",
}

HONEY_HIVE_FIELD = {"blue": "pine tree", "red": "pepper", "white": "pineapple", "mixed": "pine tree"}
GOO_FIELD = "pine tree"


def setting_key(badge_id):
    """sunflower -> sunflower_badge, blue flower -> blue_flower_badge"""
    return f"{badge_id.replace(' ', '_')}_badge"


def badge_id_from_task(task):
    """badge_blue_flower -> blue flower"""
    return task[len("badge_"):].replace("_", " ")


def get_badge(badge_id):
    """Returns {id, display_name, kind} or None."""
    badge_id = str(badge_id).replace("_", " ").strip().lower()
    if badge_id in FIELD_BADGES:
        return {"id": badge_id, "display_name": FIELD_BADGES[badge_id], "kind": "field"}
    if badge_id in ("goo", "honey"):
        return {"id": badge_id, "display_name": badge_id.title(), "kind": badge_id}
    return None


def resolve_gather_field(badge_id, hive_color="mixed"):
    entry = get_badge(badge_id)
    if entry["kind"] == "field":
        return entry["id"]
    if entry["kind"] == "goo":
        return GOO_FIELD
    return HONEY_HIVE_FIELD.get(str(hive_color).lower(), HONEY_HIVE_FIELD["mixed"])


def gather_overrides(settings, entry, field):
    """Field settings a badge gather overrides, from the Badges tab."""
    until = settings.get("badge_gather_until", "time")
    mins = settings.get("badge_gather_mins", 0)
    overrides = {"infinite_gather": False, "plant_sprout": False}
    if until == "time":
        # Only the clock ends a timed gather. A Honey Wreath wait would hold it open for a backpack that never reaches 101%.
        overrides["backpack"] = 101
        overrides["honey_wreath_return"] = False
        if mins:
            overrides["mins"] = mins
    else:
        overrides["mins"] = 999
        # The Hive Hub backpack can't be read, so it runs timed cycles instead.
        if field == "hive hub":
            overrides["mins"] = mins or 5
    if settings.get("badge_gather_return", "no override") != "no override":
        overrides["return"] = settings["badge_gather_return"]
    if entry["kind"] == "goo":
        overrides["goo"] = True
        overrides["goo_interval"] = 3
    if settings.get("badge_use_ai_gather", False):
        overrides.update(shape="fuzzy_ai_gather", start_location="center", shift_lock=False,
                         invert_lr=False, invert_fb=False,
                         ai_gather_model=settings.get("ai_gather_model", "Standard"))
    return overrides
