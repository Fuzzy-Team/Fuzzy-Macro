"""Token names and ordering from gather.js and collect.js, kept in one place."""

TOKEN_NAMES_BY_MODEL = {
    'standard': (
        'Activated Target',
        'Baby Love',
        'Beamstorm',
        'Beesmas Cheer Token',
        'Black Bear Morph',
        'Bloom',
        'Blue Bomb Sync',
        'Blue Boost',
        'Blueberry',
        'Bomb',
        'Brown Bear Morph',
        'Coconut',
        'ComboCoconut',
        'Duped Baby Love',
        'Duped Beamstorm',
        'Duped Beesmas Cheer Token',
        'Duped Black Bear Morph',
        'Duped Blue Bomb Sync',
        'Duped Blue Boost',
        'Duped Blueberry',
        'Duped Bomb',
        'Duped Brown Bear Morph',
        'Duped Festive Blessing Token',
        'Duped Festive Gift Token',
        'Duped Festive Mark Token',
        'Duped Fetch',
        'Duped Flame Fuel',
        'Duped Focus',
        'Duped Fuzz Bombs Token',
        'Duped Glitch Token',
        'Duped Glob',
        'Duped Gumdrop Barrage',
        'Duped Haste',
        'Duped Honey Mark Token',
        'Duped Honey Token',
        'Duped Impale',
        'Duped Inferno Token',
        'Duped Inflate Balloons',
        'Duped Inspire Token',
        'Duped Jelly Bean',
        'Duped Map Corruption',
        'Duped Mark Surge Token',
        'Duped Melody',
        'Duped Mind Hack',
        'Duped Mother Bear Morph',
        'Duped Panda Bear Morph',
        'Duped Pineapple',
        'Duped Polar Bear Morph',
        'Duped Pollen Haze',
        'Duped Pollen Mark Token',
        'Duped Pulse',
        'Duped Puppy Love',
        'Duped Rage Token',
        'Duped Rain Cloud',
        'Duped Red Bomb Sync',
        'Duped Red Boost',
        'Duped Science Bear Morph',
        'Duped Scratch',
        'Duped Snowflake',
        'Duped Snowglobe Shake',
        'Duped Strawberry',
        'Duped Summon Frog Token',
        'Duped Sunflower Seed',
        'Duped Surprise Party',
        'Duped Tabby Love',
        'Duped Target Practice Token',
        'Duped Token Link',
        'Duped Tornado',
        'Duped Treat',
        'Duped Triangulate Token',
        'Duped White Boost',
        'Falling Star',
        'Festive Blessing Token',
        'Festive Gift Token',
        'Festive Mark Station',
        'Festive Mark Token',
        'Fetch',
        'Flame Fuel',
        'Focus',
        'Fully Collected Target',
        'Fuzz Bombs Token',
        'Glitch Token',
        'Glob',
        'Gumdrop Barrage',
        'Haste',
        'Honey Mark Station',
        'Honey Mark Token',
        'Honey Token',
        'Impale',
        'Inferno Token',
        'Inflate Balloons',
        'Inspire Token',
        'Jelly Bean',
        'Map Corruption',
        'Mark Surge Token',
        'Melody',
        'Mind Hack',
        'Mother Bear Morph',
        'Panda Bear Morph',
        'Pineapple',
        'Polar Bear Morph',
        'Pollen Haze',
        'Pollen Mark Station',
        'Pollen Mark Token',
        'Precise Mark Station',
        'Precise Mark Target',
        'Pulse',
        'Puppy Love',
        'Rage Token',
        'Rain Cloud',
        'Red Bomb Sync',
        'Red Boost',
        'Science Bear Morph',
        'Scratch',
        'Smiley',
        'Snowflake',
        'Snowglobe Shake',
        'Strawberry',
        'Summon Frog Token',
        'Sunflower Seed',
        'Surprise Party',
        'Tabby Love',
        'Target Practice Token',
        'TennisBall',
        'Token Link',
        'Tornado',
        'Treat',
        'Triangulate Token',
        'Unactivated Target',
        'White Boost',
    ),
    'light': (
        'Baby Love',
        'Bear Morph',
        'Bomb',
        'Boost',
        'Festive Gift Token',
        'Focus',
        'Summon Frog Token',
        'Fuzz Bombs Token',
        'Haste',
        'Honey Token',
        'Inflate Balloons',
        'Inspire Token',
        'Loot',
        'Mark',
        'Melody',
        'Party Balloons',
        'Tabby Love',
        'Token Link',
    ),
    'mini': (
        'Balloon',
        'Bear Morph',
        'Bomb',
        'Boost',
        'Summon Frog Token',
        'Haste',
        'Inspire Token',
        'Long Buff',
        'Loot',
        'Mark',
        'Token Link',
    ),
}

COMMON_IGNORED_TOKENS = tuple(
    token for token in TOKEN_NAMES_BY_MODEL["standard"] if token.startswith("Duped ")
) + ("Bloom", "Honey Token", "Blueberry")

SPROUT_TOKEN_PRIORITY = (
    "Token Link", "Coconut", "Pineapple", "Blueberry", "Strawberry",
    "Sunflower Seed", "Jelly Bean", "Snowflake", "Beesmas Cheer Token",
    "Festive Blessing Token", "Treat", "Honey Token",
)
SPROUT_FIELD_TOKENS = {
    "sunflower": ("Sunflower Seed",), "pineapple": ("Pineapple",),
    "strawberry": ("Strawberry",), "coconut": ("Coconut",),
    "blue flower": ("Blueberry",), "bamboo": ("Blueberry",),
    "pine tree": ("Blueberry",), "stump": ("Blueberry",),
    "mushroom": ("Strawberry",), "rose": ("Strawberry",),
    "pepper": ("Strawberry",),
}


def token_model(model, sprouts=False):
    value = str(model or "standard").strip().lower()
    if sprouts:
        value = "_".join(value.replace("-", "_").split())
        if value in ("token_light", "loot_light", "light"):
            return "light"
        if value in ("token_mini", "loot_mini", "mini"):
            return "mini"
    return value if value in TOKEN_NAMES_BY_MODEL else "standard"


def hidden_sprout_token(token):
    return token == "Bloom" or token.startswith("Duped ")


def token_names(model="standard", sprouts=False):
    names = TOKEN_NAMES_BY_MODEL[token_model(model, sprouts)]
    return tuple(token for token in names if not hidden_sprout_token(token)) if sprouts else names


def token_state(ranking, model="standard", sprouts=False):
    names = token_names(model, sprouts)
    preferred = [token.strip() for token in (ranking.get("preferred_tokens") or "").split(",") if token.strip()]
    ignored = set(token.strip() for token in (ranking.get("ignored_tokens") or "").split(",") if token.strip())
    ordered = []
    for token in preferred + list(names):
        if token in names and token not in ordered:
            ordered.append(token)
    return [(token, token not in ignored) for token in ordered]


def token_ranking(state, model="standard", sprouts=False):
    preferred = [token for token, enabled in state if enabled]
    ignored = ([token for token in TOKEN_NAMES_BY_MODEL[token_model(model, True)]
                if hidden_sprout_token(token)] if sprouts else [])
    ignored.extend(token for token, enabled in state if not enabled and token not in ignored)
    return dict(preferred_tokens=",".join(preferred), ignored_tokens=",".join(ignored))


def sprout_preset(preset, field_name, model="standard"):
    names = token_names(model, True)
    preferred = []
    if preset == "all":
        preferred = list(names)
    elif preset == "field":
        for token in list(SPROUT_FIELD_TOKENS.get(field_name, ())) + list(names):
            if token in names and token not in preferred:
                preferred.append(token)
    ignored = [token for token in TOKEN_NAMES_BY_MODEL[token_model(model, True)]
               if hidden_sprout_token(token) or token not in preferred]
    return dict(preferred_tokens=",".join(preferred), ignored_tokens=",".join(ignored))
