"""Test Auto Planters' wax goal ranking without launching the macro."""

import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import modules.misc.planterRewards as planterRewards  # noqa: E402


CATALOG = planterRewards.loadCatalog(ROOT / "src/data/bss/planter_rewards.json")
RANKINGS = json.loads((ROOT / "src/data/bss/auto_planter_ranking.json").read_text())


def reward(goal, planter, field, growHours=6.0):
    return planterRewards.evaluateReward(CATALOG, goal, planter, field, growHours)


def key(goal, planter, field, nectarScore=0.0, growHours=6.0):
    return planterRewards.placementKey(reward(goal, planter, field, growHours), nectarScore)


class CatalogTests(unittest.TestCase):
    def test_catalog_covers_every_planter_option(self):
        rankedPlanters = {planter["name"] for planters in RANKINGS.values() for planter in planters}
        self.assertTrue(rankedPlanters <= set(CATALOG["planters"]))
        self.assertEqual(len(CATALOG["planters"]), 14)

    def test_affinity_fields_exist(self):
        for affinity in CATALOG["field_affinities"]:
            self.assertTrue(set(affinity["fields"]) <= set(RANKINGS), affinity)
            self.assertIn(affinity["wax"], CATALOG["waxes"])


class GoalTests(unittest.TestCase):
    def test_unknown_goal_falls_back_to_nectar(self):
        self.assertEqual(planterRewards.normalizeGoal("bogus"), "nectar")
        self.assertEqual(planterRewards.normalizeGoal(None), "nectar")
        self.assertEqual(planterRewards.normalizeGoal("Any Wax"), "any_wax")
        self.assertFalse(planterRewards.isWaxGoal("nectar"))
        self.assertTrue(planterRewards.isWaxGoal("hard"))

    def test_nectar_goal_has_no_wax_evidence(self):
        self.assertEqual(reward("nectar", "red clay", "pumpkin")["tier"], planterRewards.TIER_FALLBACK)


class RankingTests(unittest.TestCase):
    def test_red_clay_guarantee_beats_soft_preferences(self):
        self.assertEqual(reward("soft", "red clay", "clover")["tier"], planterRewards.TIER_GUARANTEED)
        self.assertGreater(key("soft", "red clay", "clover"), key("soft", "plastic", "pumpkin", nectarScore=100, growHours=2))

    def test_nectar_cannot_overturn_wax_rank(self):
        self.assertGreater(key("hard", "red clay", "clover", nectarScore=0.1), key("hard", "plastic", "clover", nectarScore=50))

    def test_nectar_breaks_wax_ties(self):
        self.assertGreater(key("hard", "plastic", "clover", nectarScore=2), key("hard", "candy", "clover", nectarScore=1))

    def test_field_affinities(self):
        self.assertGreater(reward("hard", "plastic", "pumpkin")["score"], reward("hard", "plastic", "clover")["score"])
        self.assertGreater(reward("caustic", "pesticide", "bamboo")["score"], reward("caustic", "pesticide", "clover")["score"])
        # Red Clay's Swirled preference only exists in blue fields
        self.assertEqual(reward("swirled", "red clay", "clover")["tier"], planterRewards.TIER_FALLBACK)
        self.assertEqual(reward("swirled", "red clay", "pine tree")["tier"], planterRewards.TIER_PREFERENCE)

    def test_field_bonus_does_not_invent_wax_for_planters_without_it(self):
        self.assertEqual(reward("soft", "blue clay", "pumpkin")["tier"], planterRewards.TIER_FALLBACK)

    def test_very_rare_drops_do_not_count(self):
        self.assertEqual(reward("caustic", "plastic", "rose")["tier"], planterRewards.TIER_FALLBACK)

    def test_shorter_growth_wins_equal_preference(self):
        self.assertGreater(reward("hard", "plastic", "clover", 2)["score"], reward("hard", "hydroponic", "clover", 12)["score"])

    def test_more_wax_slots_beat_more_nectar(self):
        wax = key("hard", "plastic", "clover")
        nectar = planterRewards.placementKey(reward("nectar", "petal", "clover"), 50)
        twoWax = planterRewards.addKeys(wax, wax)
        waxAndNectar = planterRewards.addKeys(wax, nectar)
        self.assertGreater(twoWax, waxAndNectar)
        # A nectar fallback still beats leaving the slot empty
        self.assertGreater(waxAndNectar, planterRewards.addKeys(wax, planterRewards.ZERO_KEY))


if __name__ == "__main__":
    unittest.main()
