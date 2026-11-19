'''
Planter drops that need a planter grown fully in a set field, on a cooldown in days.
Monthly waxes and singles take one harvest. Sequences and repeats need one fully grown
harvest per field in order, with the same planter, before the cooldown starts.

The auto planters task asks choosePicks for placements before its normal picks,
then calls trackHarvest after every successful harvest. Cooldowns and chain progress live in
data/user/planter_bonus_loot.json as {key: next eligible epoch time, name_counter: next field index}.
'''
import time
import modules.misc.settingsManager as settingsManager
from modules.macro.game_data import nectarFields

# (planter, field, cooldown key, days)
WAXES = [
    ('petal', 'dandelion', 'petal_caustic', 31),
    ('petal', 'strawberry', 'petal_swirl', 31),
    ('hydroponic', 'coconut', 'hydroponic_caustic', 31),
    ('hydroponic', 'mushroom', 'hydroponic_swirl', 31),
    ('heat-treated', 'coconut', 'heat_treated_caustic', 31),
    ('heat-treated', 'blue flower', 'heat_treated_swirl', 31),
    ('pesticide', 'strawberry', 'pesticide_swirl', 31),
    ('tacky', 'bamboo', 'tacky_caustic', 31),
    ('tacky', 'pumpkin', 'tacky_swirl', 31),
    ('blue_clay', 'clover', 'blue_clay_caustic', 31),
    ('blue_clay', 'spider', 'blue_clay_swirl', 31),
    ('red_clay', 'clover', 'red_clay_caustic', 31),
    ('red_clay', 'sunflower', 'red_clay_swirl1', 31),
    ('red_clay', 'pine tree', 'red_clay_swirl2', 7),
    ('candy', 'mountain top', 'candy_caustic', 31),
    ('candy', 'cactus', 'candy_swirl', 31),
    ('plastic', 'rose', 'plastic_caustic', 31),
    ('plastic', 'coconut', 'plastic_swirl', 31),
]
SINGLES = [
    ('tacky', 'mountain top', 'tacky_loaded', 31),
    ('pesticide', 'strawberry', 'pesticide_bitters1', 31),
    ('planter_of_plenty', 'bamboo', 'planter_of_plenty_super', 31),
]
# (planter, fields in harvest order, name, days)
SEQUENCES = [
    ('red_clay', ['clover', 'spider', 'cactus'], 'red_clay_stingers', 14),
    ('pesticide', ['stump', 'mountain top', 'coconut'], 'pesticide_neons', 7),
    ('heat-treated', ['mushroom', 'strawberry', 'rose', 'pepper'], 'heat_treated_red_extract', 31),
    ('hydroponic', ['blue flower', 'bamboo', 'pine tree', 'stump'], 'hydroponic_blue_extract', 31),
]
REPEATS = [
    ('candy', ['stump', 'stump', 'stump'], 'candy_glue', 7),
    ('heat-treated', ['pineapple', 'pineapple', 'pineapple'], 'heat_treated_enzymes', 31),
    ('hydroponic', ['sunflower', 'sunflower', 'sunflower'], 'hydroponic_oil', 31),
]
# (planter, field): (nectar multiplier, full grow hours) for every pair above
GROWTH = {
    ('blue_clay', 'clover'): (1.085, 5.53),
    ('blue_clay', 'spider'): (1, 6),
    ('candy', 'cactus'): (1, 4),
    ('candy', 'mountain top'): (1, 4),
    ('candy', 'stump'): (1.2, 4),
    ('heat-treated', 'blue flower'): (1, 12),
    ('heat-treated', 'coconut'): (1.03, 11.66),
    ('heat-treated', 'mushroom'): (1.8795, 8.94),
    ('heat-treated', 'pepper'): (2.044, 8.22),
    ('heat-treated', 'pineapple'): (1.03, 11.66),
    ('heat-treated', 'rose'): (1.974, 8.52),
    ('heat-treated', 'strawberry'): (1.345, 8.93),
    ('hydroponic', 'bamboo'): (1.925, 8.73),
    ('hydroponic', 'blue flower'): (1.883, 8.93),
    ('hydroponic', 'coconut'): (1.4322, 11.74),
    ('hydroponic', 'mushroom'): (1, 12),
    ('hydroponic', 'pine tree'): (1.988, 8.46),
    ('hydroponic', 'stump'): (1.375, 8.73),
    ('hydroponic', 'sunflower'): (1.075, 11.17),
    ('pesticide', 'coconut'): (1, 10),
    ('pesticide', 'mountain top'): (1, 10),
    ('pesticide', 'strawberry'): (1.6, 6.25),
    ('pesticide', 'stump'): (1.3, 10),
    ('petal', 'dandelion'): (2.13525, 9.84),
    ('petal', 'strawberry'): (1.155, 12.13),
    ('planter_of_plenty', 'bamboo'): (1.5, 16),
    ('plastic', 'coconut'): (1, 2),
    ('plastic', 'rose'): (1, 2),
    ('red_clay', 'cactus'): (1.29, 5.42),
    ('red_clay', 'clover'): (1.302, 5.53),
    ('red_clay', 'pine tree'): (1, 6),
    ('red_clay', 'spider'): (1, 6),
    ('red_clay', 'sunflower'): (1.2501, 5.76),
    ('tacky', 'bamboo'): (1.25, 8),
    ('tacky', 'mountain top'): (1, 8),
    ('tacky', 'pumpkin'): (1.25, 8),
}
# Nectar is counted in hours, 24 being full. A nectar at or above this is left alone.
NECTAR_TARGET_HOURS = 23.37
NECTAR_FULL_HOURS = 24
STATE_FILE = "planter_bonus_loot.json"

FIELD_NECTAR = {field: nectar for nectar, fields in nectarFields.items() for field in fields}


def planterKey(planter):
    '''Planter names as the auto planter settings use them: "red_clay", "heat-treated"'''
    return str(planter or "").lower().replace(" ", "_")


def fieldKey(field):
    return str(field or "").lower().replace("_", " ")


def dropPlanters():
    '''The planters each drop setting can use, so the GUI only offers a drop when one of them is selected'''
    return {
        "planter_monthly_waxes": sorted({row[0] for row in WAXES}),
        "planter_bonus_loot": sorted({row[0] for row in SINGLES + SEQUENCES + REPEATS}),
    }


def enabled(setdat):
    return bool(setdat.get("planter_monthly_waxes") or setdat.get("planter_bonus_loot"))


def growHours(planter, field, degradationHours=0):
    return GROWTH[(planterKey(planter), fieldKey(field))][1] + degradationHours


def fullyGrown(planter, field, placedTime, growSeconds=None):
    '''None when the placement time is unknown. One minute of slack.'''
    pair = (planterKey(planter), fieldKey(field))
    if pair not in GROWTH:
        return False
    if not placedTime:
        return None
    if growSeconds is None:
        growSeconds = GROWTH[pair][1] * 3600
    return time.time() - placedTime >= growSeconds - 60


def loadState():
    try:
        state = settingsManager.loadUserJson(STATE_FILE)
    except Exception:
        return {}
    return state if isinstance(state, dict) else {}


def saveState(state):
    settingsManager.saveUserJson(STATE_FILE, state)


def offCooldown(state, key, now):
    return float(state.get(key, 0) or 0) <= now


def counter(state, name):
    return int(state.get(name + "_counter", 0) or 0)


def plantable(setdat, planter, field):
    return bool(setdat.get(f"auto_planter_{planter}_field_{field.replace(' ', '_')}", True))


def fieldEnabled(setdat, field):
    return bool(setdat.get(f"auto_field_{field.replace(' ', '_')}", False))


def planterEnabled(setdat, planter):
    return bool(setdat.get(f"auto_planter_{planterKey(planter)}", False))


def choosePicks(setdat, allowedPlanters, disallowedFields, numberToPlant, nectarHours, degradationHours):
    '''
    Returns ([(planter, field)], lockedPlanters). Locked planters are partway through a chain
    and must not be used elsewhere. nectarHours ({nectar: hours}) orders picks by nectar need.
    '''
    picks, lockedPlanters = [], []
    if not enabled(setdat):
        return picks, lockedPlanters
    now = time.time()
    state = loadState()
    allowedPlanters = {planterKey(p) for p in allowedPlanters}
    disallowedFields = {fieldKey(f) for f in disallowedFields}

    def usable(p, f):
        return p in allowedPlanters and f not in disallowedFields and f in FIELD_NECTAR and plantable(setdat, p, f)

    def canFinish(p, fields):
        return all(fieldEnabled(setdat, f) and f in FIELD_NECTAR and plantable(setdat, p, f) for f in fields)

    def free(p, f, key):
        return usable(p, f) and p not in lockedPlanters and offCooldown(state, key, now)

    chains = SEQUENCES + REPEATS if setdat.get("planter_bonus_loot") else []
    candidates = []
    for p, fields, name, _ in chains:
        count = counter(state, name)
        if count != 0 and canFinish(p, fields):
            if p not in lockedPlanters:
                lockedPlanters.append(p)
            f = fields[min(count, len(fields) - 1)]
            if usable(p, f):
                candidates.append((p, f))

    others = []
    if setdat.get("planter_monthly_waxes"):
        others += [(p, f, [f]) for p, f, key, _ in WAXES if free(p, f, key)]
    if setdat.get("planter_bonus_loot"):
        others += [(p, f, [f]) for p, f, key, _ in SINGLES if free(p, f, key)]
    chainStarts = [
        (p, fields[0], fields) for p, fields, name, _ in chains
        if counter(state, name) == 0 and canFinish(p, fields) and free(p, fields[0], name + "_datetime")
    ]

    takenPlanters, takenFields = set(), set()
    remainingNectarHours = dict(nectarHours)

    def take(p, f):
        picks.append((p, f))
        takenPlanters.add(p)
        takenFields.add(f)
        multiplier, growth = GROWTH[(p, f)]
        nectar = FIELD_NECTAR[f]
        remainingNectarHours[nectar] = min(
            NECTAR_FULL_HOURS, remainingNectarHours.get(nectar, 0) + growth * multiplier
        )

    for p, f in candidates:
        if len(picks) == numberToPlant:
            break
        if p not in takenPlanters and f not in takenFields:
            take(p, f)
    for tier in (others, chainStarts):
        if len(picks) == numberToPlant:
            break
        tier = [row for row in tier if row[0] not in takenPlanters and row[1] not in takenFields]
        for p, f in orderPicks(setdat, tier, remainingNectarHours, degradationHours):
            if len(picks) == numberToPlant:
                break
            if p not in takenPlanters and f not in takenFields:
                take(p, f)
    return picks, lockedPlanters


def nectarOrder(setdat):
    '''Nectars in the auto planter priority order'''
    order = []
    for i in range(5):
        nectar = setdat.get(f"auto_priority_{i}_nectar", "none")
        if nectar != "none" and nectar not in order:
            order.append(nectar)
    return order


def orderPicks(setdat, others, nectarHours, degradationHours):
    '''
    Each next pick is the one that best fills the most wanted nectar still under the target,
    per hour of growth. Picks that fill no wanted nectar go last, shortest to finish first.
    '''
    rows = []
    for p, f, fields in others:
        multiplier, growth = GROWTH[(p, f)]
        degradation = degradationHours(f)
        rowGrowHours = growth + degradation
        hours = rowGrowHours + sum(GROWTH[(p, other)][1] for other in fields[1:])
        rows.append({
            "planter": p, "field": f, "nectar": FIELD_NECTAR[f], "gain": growth * multiplier,
            "grow_hours": rowGrowHours, "key": (hours, round(degradation)),
        })
    left = sorted(rows, key=lambda row: row["key"])
    amounts = dict(nectarHours)
    ordered = []
    while left:
        best = None
        for nectar in nectarOrder(setdat):
            if nectar not in amounts or amounts[nectar] >= NECTAR_TARGET_HOURS:
                continue
            options = [row for row in left if row["nectar"] == nectar]
            if not options:
                continue

            def useful(row):
                remaining = max(0, amounts[nectar] - row["grow_hours"])
                return min(row["gain"], NECTAR_TARGET_HOURS - remaining)
            best = sorted(options, key=lambda row: -useful(row) / row["grow_hours"])[0]
            break
        if best is None:
            ordered += left
            break
        ordered.append(best)
        left.remove(best)
        amounts[best["nectar"]] = min(NECTAR_FULL_HOURS, amounts[best["nectar"]] + best["gain"])
    return [(row["planter"], row["field"]) for row in ordered]


def trackHarvest(planter, field, isFullyGrown):
    '''
    Call after a successful harvest. isFullyGrown is None when the placement time is unknown,
    in which case nothing is recorded.
    '''
    if isFullyGrown is None:
        return
    planter, field = planterKey(planter), fieldKey(field)
    now = time.time()
    state = loadState()
    changed = False
    for p, f, key, days in WAXES + SINGLES:
        if p == planter and f == field and isFullyGrown and offCooldown(state, key, now):
            state[key] = now + days * 86400
            changed = True
    for p, fields, name, days in SEQUENCES + REPEATS:
        if p != planter:
            continue
        count = counter(state, name)
        lastIndex = len(fields) - 1
        correctHarvest = (isFullyGrown and field == fields[min(count, lastIndex)]
                          and (count != 0 or offCooldown(state, name + "_datetime", now)))
        if not correctHarvest:
            if count != 0:
                state[name + "_counter"] = 0
                changed = True
        elif min(count, lastIndex) == lastIndex:
            state[name + "_counter"] = 0
            state[name + "_datetime"] = now + days * 86400
            changed = True
        else:
            state[name + "_counter"] = count + 1
            changed = True
    if changed:
        saveState(state)
