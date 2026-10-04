"""Exercise production route logic without launching Roblox or screen controls."""

import ast
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ast.parse((ROOT / 'src/main.py').read_text())
MACRO_SOURCE = ast.parse((ROOT / 'src/modules/macro.py').read_text())
DROPS = ast.literal_eval(next(
    node.value for node in MACRO_SOURCE.body
    if isinstance(node, ast.Assign)
    and any(isinstance(target, ast.Name) and target.id == 'specialPlanterDrops'
            for target in node.targets)
))


class SpecialDropTests(unittest.TestCase):
    def setUp(self):
        names = {'getSpecialDropById', 'canPlaceSpecialDrop',
                 'findBestSpecialDropPlacement', 'completeSpecialDropStep',
                 'getNaturalPlanterProgress'}
        module = ast.Module(body=[node for node in ast.walk(SOURCE)
                                  if isinstance(node, ast.FunctionDef) and node.name in names],
                            type_ignores=[])
        self.now = 1000000
        self.state = {}
        self.blocked = set()
        self.blocked_placements = set()
        self.macro = SimpleNamespace(setdat={f"auto_planter_{drop['planter'].replace(' ', '_')}": True
                                            for drop in DROPS}, logger=SimpleNamespace(webhook=Mock()))
        self.ns = dict(macroModule=SimpleNamespace(specialPlanterDrops=DROPS),
                       macro=self.macro, specialDropState=self.state,
                       blockedPlanters=self.blocked, blockedPlacements=self.blocked_placements,
                       time=SimpleNamespace(time=lambda: self.now),
                       fieldToNectar={}, getTotalNectarPercent=lambda nectar: 0,
                       getPriorityInfo=lambda nectar: {'min': 80},
                       getPlanterRanking=lambda field, planter: {'name': planter},
                       getEffectiveNaturalGrowTimeSeconds=lambda field, planter: 3600,
                       estimateNectarGain=lambda planter, seconds: 10,
                       getFieldDegradationHours=lambda field: 0)
        exec(compile(module, str(ROOT / 'src/main.py'), 'exec'), self.ns)
        self.drop = next(drop for drop in DROPS if drop['id'] == 'candy_stump_glue')

    def placement(self, fields=None, planters=None):
        return self.ns['canPlaceSpecialDrop'](self.drop, fields or set(), planters or set(), {})

    def harvest(self, field='stump', age=3600):
        self.ns['completeSpecialDropStep'](dict(
            special_drop_id=self.drop['id'], planter=self.drop['planter'], field=field,
            placed_time=self.now - age, natural_grow_duration=3600,
            harvest_time=self.now - age + 3600))

    def test_missing_inventory_is_not_retried_on_another_route(self):
        self.blocked.add('candy')
        other = next(drop for drop in DROPS if drop['id'] == 'candy_cactus_swirled_wax')
        self.assertIsNone(self.ns['findBestSpecialDropPlacement'](
            [self.drop, other], set(), set(), {}))

    def test_missing_inventory_failure_blocks_planter_in_scheduler(self):
        # Execute the production failure handler, including its inventory distinction.
        node = next(node for node in ast.walk(SOURCE)
                    if isinstance(node, ast.If) and isinstance(node.test, ast.Name)
                    and node.test.id == 'specialPlacement')
        attempt = next(child for child in node.body if isinstance(child, ast.If))
        self.macro.lastPlanterPlacementFailure = 'missing_inventory'
        self.ns['specialPlacement'] = {'planter': 'candy', 'field': 'stump'}
        exec(compile(ast.Module(body=node.body[node.body.index(attempt) + 1:],
                                type_ignores=[]), '<special-placement-failure>', 'exec'), self.ns)
        self.assertIn('candy', self.blocked)
        self.assertIsNone(self.placement())

    def test_field_failure_only_blocks_failed_placement(self):
        self.blocked_placements.add(('candy', 'stump'))
        other = next(drop for drop in DROPS if drop['id'] == 'candy_cactus_swirled_wax')
        selected = self.ns['findBestSpecialDropPlacement']([self.drop, other], set(), set(), {})
        self.assertEqual(selected['field'], 'cactus')

    def test_disabled_or_occupied_planter_is_not_placed(self):
        self.assertIsNone(self.placement(planters={'candy'}))
        self.macro.setdat['auto_planter_candy'] = False
        self.assertIsNone(self.placement())

    def test_occupied_field_is_not_placed(self):
        self.assertIsNone(self.placement(fields={'stump'}))

    def test_special_route_waits_for_full_growth(self):
        plan = self.placement()['plan']
        self.assertEqual(plan['grow_duration'], 3600)
        self.assertEqual(plan['harvest_time'], self.now + 3600)
        self.harvest(age=1800)
        self.assertEqual(self.state, {})

    def test_repeated_field_route_requires_three_harvests(self):
        self.harvest()
        self.assertEqual(self.state[self.drop['id']]['progress'], 1)
        self.harvest()
        self.assertEqual(self.state[self.drop['id']]['progress'], 2)
        self.harvest()
        self.assertEqual(self.state[self.drop['id']]['progress'], 0)
        deadline = self.now + 7 * 86400
        self.assertEqual(self.state[self.drop['id']]['cooldown_until'], deadline)
        self.assertIsNone(self.placement())
        self.now = deadline
        self.assertIsNotNone(self.placement())

    def test_wrong_field_resets_progress_without_starting_cooldown(self):
        self.state[self.drop['id']] = {'progress': 1, 'cooldown_until': 0}
        self.harvest(field='cactus')
        self.assertEqual(self.state[self.drop['id']], {'progress': 0, 'cooldown_until': 0})

    def test_next_field_follows_saved_progress(self):
        self.drop = next(drop for drop in DROPS if drop['id'] == 'red_clay_clover_spider_cactus_stingers')
        self.harvest(field='clover')
        self.assertEqual(self.placement()['field'], 'spider')

    def save_placement(self, plan):
        function = copy.deepcopy(next(node for node in ast.walk(SOURCE)
                                      if isinstance(node, ast.FunctionDef)
                                      and node.name == 'savePlacedPlanter'))
        function.body = [node for node in function.body if not isinstance(node, ast.Nonlocal)]
        slots = [{}]
        self.ns.update(planterData=slots, nectarLastFields={},
                       saveAutoPlanterData=Mock(), sendNectarPercentageWebhook=Mock())
        self.ns['time'].strftime = lambda *args: '01:00:00'
        self.ns['time'].gmtime = lambda seconds: seconds
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<save-placement>', 'exec'), self.ns)
        self.ns['savePlacedPlanter'](0, 'stump', {'name': 'candy'}, 'comforting', plan)
        self.ns['saveAutoPlanterData'].assert_called_once()
        return slots[0]

    def test_full_growth_starts_after_travel_and_successful_placement(self):
        plan = self.placement()['plan']
        selected_at = self.now
        self.now += 120
        saved = self.save_placement(plan)
        self.assertEqual(saved['placed_time'], self.now)
        self.assertEqual(saved['harvest_time'], self.now + 3600)
        self.assertEqual(saved['special_drop_id'], self.drop['id'])
        self.assertEqual(plan['placed_time'], selected_at)

    def test_normal_planters_keep_their_synchronized_harvest_deadline(self):
        plan = self.placement()['plan']
        plan['special_drop_id'] = ''
        self.now += 120
        saved = self.save_placement(plan)
        self.assertEqual(saved['placed_time'], plan['placed_time'])
        self.assertEqual(saved['harvest_time'], plan['harvest_time'])


if __name__ == '__main__':
    unittest.main()
