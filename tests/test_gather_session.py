import os
import tempfile
import unittest

from src.modules.gather_session import GatherPatternRunner, GatherSession


class GatherPatternRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = self.temp_dir.name
        self.installed = os.path.join(self.root, "settings", "patterns")
        self.defaults = os.path.join(self.root, "settings", "defaults", "patterns")
        os.makedirs(self.installed)
        os.makedirs(self.defaults)
        self.alerts = []
        self.write("e_lol", "cycles.append('fallback')", shipped=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def write(self, name, source, shipped=False, installed=True):
        if shipped:
            with open(os.path.join(self.defaults, f"{name}.py"), "w") as handle:
                handle.write(source)
        if installed:
            with open(os.path.join(self.installed, f"{name}.py"), "w") as handle:
                handle.write(source)

    def runner(self, pattern):
        return GatherPatternRunner(
            self.root,
            pattern,
            alert=lambda failed, error: self.alerts.append((failed, error)),
        )

    def test_unchanged_builtin_is_compiled_once(self):
        self.write("lines", "cycles.append('lines')", shipped=True)
        runner = self.runner("lines")
        namespace = {"cycles": []}
        runner.run_cycle(namespace)
        runner.run_cycle(namespace)
        self.assertTrue(runner.is_builtin())
        self.assertEqual(namespace["cycles"], ["lines", "lines"])
        self.assertEqual(list(runner._compiled), ["lines"])
        self.assertEqual(runner._compiled["lines"].__name__, "run_lines")

    def test_edited_builtin_runs_the_users_file(self):
        self.write("lines", "cycles.append('default')", shipped=True, installed=False)
        self.write("lines", "cycles.append('edited')")
        runner = self.runner("lines")
        namespace = {"cycles": []}
        runner.run_cycle(namespace)
        self.assertFalse(runner.is_builtin())
        self.assertEqual(namespace["cycles"], ["edited"])

    def test_builtin_edited_mid_session_runs_the_users_file(self):
        self.write("lines", "cycles.append('default')", shipped=True)
        runner = self.runner("lines")
        namespace = {"cycles": []}
        runner.run_cycle(namespace)
        self.write("lines", "cycles.append('edited!')")
        runner.run_cycle(namespace)
        self.assertEqual(namespace["cycles"], ["default", "edited!"])

    def test_custom_failure_alerts_once_and_falls_back_for_session(self):
        self.write("custom", "raise RuntimeError('broken move')")
        runner = self.runner("custom")
        namespace = {"cycles": []}
        first = runner.run_cycle(namespace)
        second = runner.run_cycle(namespace)
        self.assertTrue(first.fell_back)
        self.assertEqual(second.pattern, "e_lol")
        self.assertEqual(namespace["cycles"], ["fallback", "fallback"])
        self.assertEqual(self.alerts, [("custom", "broken move")])

    def test_failure_uses_shipped_fallback_even_if_user_edited_e_lol(self):
        self.write("e_lol", "cycles.append('edited fallback')")
        self.write("custom", "raise RuntimeError('broken move')")
        runner = self.runner("custom")
        namespace = {"cycles": []}
        runner.run_cycle(namespace)
        self.assertEqual(namespace["cycles"], ["fallback"])

    def test_ai_runtime_error_uses_same_fallback(self):
        self.write(
            "fuzzy_ai_gather",
            "_FUZZY_AI_GATHER_STATE = {'ready': False, 'error': 'model failed'}",
        )
        runner = self.runner("fuzzy_ai_gather")
        namespace = {"cycles": []}
        result = runner.run_cycle(namespace)
        self.assertTrue(result.fell_back)
        self.assertEqual(result.pattern, "e_lol")
        self.assertEqual(self.alerts, [("fuzzy_ai_gather", "model failed")])

    def test_missing_pattern_falls_back(self):
        runner = self.runner("missing")
        namespace = {"cycles": []}
        result = runner.run_cycle(namespace)
        self.assertTrue(result.fell_back)
        self.assertEqual(namespace["cycles"], ["fallback"])

    def test_interruption_is_not_treated_as_pattern_failure(self):
        class StopGathering(Exception):
            pass

        self.write("custom", "raise StopGathering()")
        runner = GatherPatternRunner(
            self.root,
            "custom",
            alert=lambda failed, error: self.alerts.append((failed, error)),
            fatal_exceptions=(StopGathering,),
        )
        with self.assertRaises(StopGathering):
            runner.run_cycle({"StopGathering": StopGathering, "cycles": []})
        self.assertEqual(self.alerts, [])

    def test_finish_calls_pattern_cleanup(self):
        runner = self.runner("e_lol")
        calls = []
        runner.finish({"onGatherEnd": lambda: calls.append("done")})
        self.assertEqual(calls, ["done"])

    def test_absolute_paths_do_not_depend_on_working_directory(self):
        self.write("lines", "cycles.append('lines')", shipped=True)
        runner = self.runner("lines")
        namespace = {"cycles": []}
        previous = os.getcwd()
        try:
            os.chdir(os.path.dirname(self.root))
            runner.run_cycle(namespace)
        finally:
            os.chdir(previous)
        self.assertEqual(namespace["cycles"], ["lines"])

    def test_session_clock_excludes_paused_time_and_returns_outcome(self):
        self.write("lines", "cycles.append('lines')", shipped=True)
        times = iter((10.0, 12.0, 17.0, 20.0))
        session = GatherSession(self.runner("lines"), lambda: next(times))
        session.start()
        self.assertEqual(session.elapsed(True), 2.0)
        self.assertEqual(session.elapsed(False), 2.0)
        result = session.finish({"cycles": []}, "time_limit")
        self.assertEqual(result.reason, "time_limit")
        self.assertEqual(result.elapsed_seconds, 5.0)
        self.assertEqual(result.active_pattern, "lines")

    def test_session_cleanup_runs_once(self):
        session = GatherSession(self.runner("e_lol"), lambda: 10.0)
        session.start()
        calls = []
        session.add_cleanup(lambda: calls.append("report"))
        namespace = {"onGatherEnd": lambda: calls.append("pattern")}
        session.finish(namespace, "stopped")
        session.finish(namespace, "completed")
        self.assertEqual(calls, ["pattern", "report"])
        self.assertEqual(session.result.reason, "stopped")


if __name__ == "__main__":
    unittest.main()
