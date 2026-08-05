"""Bee Swarm field / goo / honey badge definitions for Badge tasks."""

BADGE_TIERS = ("cadet", "hotshot", "ace", "master", "grandmaster")

# Standard field pollen thresholds (Cadet → Grandmaster)
_STANDARD_POLLEN = (250_000, 2_500_000, 25_000_000, 250_000_000, 5_000_000_000)
_COCONUT_PEPPER_POLLEN = (50_000_000, 500_000_000, 5_000_000_000, 50_000_000_000, 1_000_000_000_000)
_HIVE_HUB_POLLEN = (10_000_000, 100_000_000, 1_000_000_000, 10_000_000_000, 100_000_000_000)
_MOUNTAIN_TOP_POLLEN = (100_000_000, 10_000_000_000, 1_000_000_000_000, 100_000_000_000_000, 1_000_000_000_000_000)
_GOO_THRESHOLDS = (500_000, 5_000_000, 50_000_000, 500_000_000, 10_000_000_000)
_HONEY_THRESHOLDS = (1_000_000, 10_000_000, 100_000_000, 1_000_000_000, 20_000_000_000)

# field key -> display name used in badge menu titles ("Sunflower Badge - Master")
FIELD_BADGES = [
    ("sunflower", "Sunflower", _STANDARD_POLLEN),
    ("dandelion", "Dandelion", _STANDARD_POLLEN),
    ("mushroom", "Mushroom", _STANDARD_POLLEN),
    ("blue flower", "Blue Flower", _STANDARD_POLLEN),
    ("clover", "Clover", _STANDARD_POLLEN),
    ("spider", "Spider", _STANDARD_POLLEN),
    ("strawberry", "Strawberry", _STANDARD_POLLEN),
    ("bamboo", "Bamboo", _STANDARD_POLLEN),
    ("pineapple", "Pineapple", _STANDARD_POLLEN),
    ("pumpkin", "Pumpkin", _STANDARD_POLLEN),
    ("cactus", "Cactus", _STANDARD_POLLEN),
    ("rose", "Rose", _STANDARD_POLLEN),
    ("pine tree", "Pine Tree", _STANDARD_POLLEN),
    ("stump", "Stump", _STANDARD_POLLEN),
    ("coconut", "Coconut", _COCONUT_PEPPER_POLLEN),
    ("pepper", "Pepper", _COCONUT_PEPPER_POLLEN),
    ("hive hub", "Hive Hub", _HIVE_HUB_POLLEN),
    ("mountain top", "Mountain Top", _MOUNTAIN_TOP_POLLEN),
]

SPECIAL_BADGES = [
    ("goo", "Goo", "goo", _GOO_THRESHOLDS),
    ("honey", "Honey", "honey", _HONEY_THRESHOLDS),
]

# Badges that cannot be progressed by gathering (excluded from UI/automation)
EXCLUDED_BADGES = (
    "quest",
    "battle",
    "ability",
    "playtime",
    "sticker stack",
)

HONEY_HIVE_FIELD = {
    "blue": "pine tree",
    "red": "pepper",
    "white": "pineapple",
    "mixed": "pine tree",
}

GOO_DEFAULT_FIELD = "pine tree"


def setting_key(badge_id):
    """Profile setting key, e.g. sunflower_badge / blue_flower_badge / goo_badge."""
    return f"{badge_id.replace(' ', '_')}_badge"


def task_id(badge_id):
    """Priority task id, e.g. badge_sunflower / badge_blue_flower."""
    return f"badge_{badge_id.replace(' ', '_')}"


def badge_id_from_task(task):
    """badge_blue_flower -> blue flower"""
    if not task.startswith("badge_"):
        return None
    return task[len("badge_"):].replace("_", " ")


def all_badge_entries():
    """
    Yield dicts:
      id, display_name, kind ('field'|'goo'|'honey'), gather_field (or None for honey/goo resolved later),
      thresholds, setting_key, task_id
    """
    for field, display, thresholds in FIELD_BADGES:
        yield {
            "id": field,
            "display_name": display,
            "kind": "field",
            "gather_field": field,
            "thresholds": thresholds,
            "setting_key": setting_key(field),
            "task_id": task_id(field),
        }
    for badge_id, display, kind, thresholds in SPECIAL_BADGES:
        yield {
            "id": badge_id,
            "display_name": display,
            "kind": kind,
            "gather_field": GOO_DEFAULT_FIELD if kind == "goo" else None,
            "thresholds": thresholds,
            "setting_key": setting_key(badge_id),
            "task_id": task_id(badge_id),
        }


def get_badge(badge_id):
    normalized = str(badge_id).replace("_", " ").strip().lower()
    for entry in all_badge_entries():
        if entry["id"] == normalized:
            return entry
    return None


def resolve_gather_field(badge_id, hive_color="mixed"):
    entry = get_badge(badge_id)
    if not entry:
        return None
    if entry["kind"] == "field":
        return entry["gather_field"]
    if entry["kind"] == "goo":
        return GOO_DEFAULT_FIELD
    if entry["kind"] == "honey":
        color = str(hive_color or "mixed").strip().lower()
        return HONEY_HIVE_FIELD.get(color, HONEY_HIVE_FIELD["mixed"])
    return None


def all_setting_keys():
    return [e["setting_key"] for e in all_badge_entries()]


def all_task_ids():
    return [e["task_id"] for e in all_badge_entries()]
