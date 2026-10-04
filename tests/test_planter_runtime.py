import ast
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from modules.misc.planterRuntime import PlanterRuntimeClock, normalize_route_runtime, route_remaining


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = str(Path(self.directory.name) / 'runtime.json')
        self.now = 10.0
        self.shared = SimpleNamespace(value=0)
        self.clock = PlanterRuntimeClock(self.path, self.shared, lambda: self.now)

    def tick(self, seconds, active):
        self.now += seconds
        self.clock.tick(active)

    def test_pause_stop_and_standby_do_not_count(self):
        self.clock.tick(True)
        self.tick(60, True)
        self.tick(1, False)
        self.tick(86400, False)
        self.tick(1, True)
        self.tick(30, True)
        self.assertEqual(self.shared.value, 90)

    def test_restart_preserves_runtime_without_counting_offline_gap(self):
        self.clock.tick(True)
        self.tick(60, True)
        self.clock.save()
        self.now += 86400
        restarted = PlanterRuntimeClock(self.path, self.shared, lambda: self.now)
        restarted.tick(True)
        self.assertEqual(self.shared.value, 60)
        self.now += 30
        restarted.tick(True)
        self.assertEqual(self.shared.value, 90)

    def test_stop_immediately_checkpoints(self):
        self.clock.tick(True)
        self.tick(2, True)
        self.tick(1, False)
        self.assertEqual(json.loads(Path(self.path).read_text())['seconds'], 2)

    def test_legacy_timestamp_does_not_credit_offline_growth(self):
        planter = dict(special_drop_id='route', natural_grow_duration=3600,
                       placed_time=1, harvest_time=3601)
        normalize_route_runtime(planter, 1000)
        self.assertEqual(route_remaining(planter, 1000), 3600)
        self.assertEqual(planter['placed_time'], 0)
        self.assertEqual(planter['harvest_time'], 0)
        self.assertEqual(route_remaining(planter, 1300), 3300)

    def test_saved_planter_keeps_its_baseline_across_reload(self):
        planter = dict(special_drop_id='route', natural_grow_duration=3600,
                       runtime_baseline=1000, growth_runtime=100)
        reloaded = json.loads(json.dumps(planter))
        normalize_route_runtime(reloaded, 1200)
        self.assertEqual(route_remaining(reloaded, 1200), 3300)
        self.assertEqual(route_remaining(reloaded, 4600), 0)

    def test_normal_planters_are_unchanged(self):
        planter = dict(placed_time=1, harvest_time=3601)
        original = dict(planter)
        normalize_route_runtime(planter, 1000)
        self.assertEqual(planter, original)

    def test_clock_checkpoint_loss_cannot_make_a_planter_ready_early(self):
        planter = dict(special_drop_id='route', natural_grow_duration=3600,
                       runtime_baseline=1000, growth_runtime=0)
        self.assertEqual(route_remaining(planter, 995), 3600)

    def test_supervisor_only_counts_a_live_running_worker(self):
        source = ast.parse((Path(__file__).resolve().parents[1] / 'src/main.py').read_text())
        call = next(node for node in ast.walk(source)
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == 'planterRuntimeClock' and node.func.attr == 'tick')
        expression = compile(ast.Expression(body=call.args[0]), '<runtime-active>', 'eval')
        for state, alive, status, standby, expected in (
                (2, True, 'gather_pine_tree', False, True),
                (3, True, 'idle_main_menu', False, False),
                (6, True, 'gather_pine_tree', False, False),
                (4, True, 'rejoining', False, False),
                (2, True, 'rejoining', False, False),
                (2, True, 'idle_main_menu', True, False),
                (2, False, 'gather_pine_tree', False, False)):
            with self.subTest(state=state, alive=alive, status=status, standby=standby):
                worker = Mock()
                worker.is_alive.return_value = alive
                self.assertEqual(eval(expression, dict(run=SimpleNamespace(value=state),
                                                       macroProc=worker, status=SimpleNamespace(value=status),
                                                       standbyState=SimpleNamespace(active=standby))), expected)


if __name__ == '__main__':
    unittest.main()
