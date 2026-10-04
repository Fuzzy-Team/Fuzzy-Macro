"""Wax goal ranking for Auto Planters.

Pure helpers so the ranking can be tested without the macro. The catalog lives in
data/bss/planter_rewards.json; its preference points are a scheduling policy, not drop rates.
"""

import json

GOALS = ("nectar", "any_wax", "soft", "hard", "caustic", "swirled")
WAX_GOALS = GOALS[1:]

TIER_FALLBACK = 0
TIER_PREFERENCE = 1
TIER_GUARANTEED = 2


def loadCatalog(path):
    with open(path, "r") as f:
        return json.load(f)


def normalizeGoal(goal):
    goal = str(goal or "nectar").strip().lower().replace(" ", "_")
    return goal if goal in GOALS else "nectar"


def isWaxGoal(goal):
    return normalizeGoal(goal) in WAX_GOALS


def _targetWaxes(catalog, goal):
    goal = normalizeGoal(goal)
    if goal == "any_wax":
        return list(catalog.get("waxes", []))
    if goal in WAX_GOALS:
        return [goal]
    return []


def _preferencePoints(catalog, planter, field, wax):
    entry = catalog.get("planters", {}).get(planter, {})
    points = entry.get("preference", {}).get(wax, 0)
    for affinity in catalog.get("field_affinities", []):
        if affinity.get("wax") != wax or field not in affinity.get("fields", []):
            continue
        affinityPlanters = affinity.get("planters")
        if affinityPlanters is not None:
            if planter in affinityPlanters:
                points += 1
        elif points > 0:
            # Field-wide wax bonuses only boost planters already known to drop that wax
            points += 1
    return points


def evaluateReward(catalog, goal, planter, field, growHours):
    """Return the wax tier and score for placing planter in field.

    Guaranteed drops rank above preference points; within a tier, more wax per hour of
    full growth wins. A tier of 0 means there is no wax evidence and nectar decides.
    """
    waxes = _targetWaxes(catalog, goal)
    entry = catalog.get("planters", {}).get(planter)
    growHours = max(0.1, float(growHours))
    if not waxes or not entry:
        return {"tier": TIER_FALLBACK, "score": 0.0, "reason": ""}

    guaranteed = sum(entry.get("guaranteed", {}).get(wax, 0) for wax in waxes)
    if guaranteed > 0:
        return {
            "tier": TIER_GUARANTEED,
            "score": guaranteed / growHours,
            "reason": f"guarantees {guaranteed} {'/'.join(waxes)} wax per full harvest",
        }

    points = sum(_preferencePoints(catalog, planter, field, wax) for wax in waxes)
    if points > 0:
        return {
            "tier": TIER_PREFERENCE,
            "score": points / growHours,
            "reason": f"wiki lists {'/'.join(waxes)} wax drops (preference {points})",
        }

    return {"tier": TIER_FALLBACK, "score": 0.0, "reason": ""}


def placementKey(reward, nectarScore):
    """Score vector for one placement. Sum vectors to compare sets lexicographically.

    Order: guaranteed placements, preference placements, guaranteed wax/hour,
    preference wax/hour, then nectar. Nectar can only break ties between equal wax plans.
    """
    tier = reward["tier"]
    return (
        1 if tier == TIER_GUARANTEED else 0,
        1 if tier == TIER_PREFERENCE else 0,
        reward["score"] if tier == TIER_GUARANTEED else 0.0,
        reward["score"] if tier == TIER_PREFERENCE else 0.0,
        float(nectarScore),
    )


def addKeys(a, b):
    return tuple(x + y for x, y in zip(a, b))


ZERO_KEY = (0, 0, 0.0, 0.0, 0.0)
