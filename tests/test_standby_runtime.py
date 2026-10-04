"""Run production supervisor code with isolated process and app controls."""

import ast
import copy
from pathlib import Path
from queue import Queue
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ast.parse((ROOT / "src/main.py").read_text())
MAIN = next(node for node in SOURCE.body if isinstance(node, ast.If) and
            isinstance(node.test, ast.Compare) and
            isinstance(node.test.left, ast.Name) and node.test.left.id == "__name__")
SUPERVISOR = next(node for node in MAIN.body if isinstance(node, ast.While))
FUNCTION_NAMES = {"startStandbyKeepAwake", "stopStandbyKeepAwake", "processStandbyCommands"}


def load_runtime(namespace):
    nodes = [copy.deepcopy(node) for node in MAIN.body if
             isinstance(node, ast.FunctionDef) and node.name in FUNCTION_NAMES]
    module = ast.parse("")
    module.body = nodes
    exec(compile(module, "src/main.py", "exec"), namespace)

    # Execute the real standby prefix of one supervisor iteration. The normal
    # macro supervisor after this prefix launches Roblox and is deliberately excluded.
    prefix = []
    for node in SUPERVISOR.body:
        prefix.append(copy.deepcopy(node))
        if (isinstance(node, ast.If) and isinstance(node.test, ast.Attribute) and
                isinstance(node.test.value, ast.Name) and
                node.test.value.id == "standbyState" and node.test.attr == "active"):
            if len(node.body) == 1 and isinstance(node.body[0], ast.Continue):
                prefix[-1].body = [ast.Break()]
                break
    prefix.append(ast.Break())
    module.body = [ast.While(test=ast.Constant(value=True), body=prefix, orelse=[])]
    ast.fix_missing_locations(module)
    return compile(module, "src/main.py", "exec")


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.process = Mock()
        self.process.poll.return_value = None
        self.ns = {
            "planterRuntimeClock": Mock(), "macroProc": Mock(),
            "standbyCommandQueue": Queue(),
            "standbyState": SimpleNamespace(active=False, deadline=0.0),
            "standbyCaffeinateProc": None,
            "run": SimpleNamespace(value=3),
            "status": SimpleNamespace(value="idle_main_menu"),
            "current_time": 1000.0,
            "time": SimpleNamespace(time=Mock(return_value=1000.0), sleep=Mock()),
            "eel": SimpleNamespace(sleep=Mock()),
            "subprocess": SimpleNamespace(Popen=Mock(return_value=self.process), DEVNULL=-3),
            "richPresenceManager": Mock(),
            "gui": Mock(), "logger": Mock(), "appManager": Mock(), "stopApp": Mock(),
        }
        self.tick_code = load_runtime(self.ns)

    def tick(self):
        exec(self.tick_code, self.ns)

    def enable(self, duration=None):
        self.ns["standbyCommandQueue"].put({"action": "enable", "duration_seconds": duration})
        self.tick()

    def test_enable_from_stopped(self):
        self.enable(1800)
        self.assertTrue(self.ns["standbyState"].active)
        self.assertEqual(self.ns["standbyState"].deadline, 2800)
        self.assertEqual(self.ns["run"].value, 3)
        self.ns["gui"].stopAllTools.assert_called_once()
        self.ns["appManager"].closeApp.assert_called_once_with("Roblox")
        self.ns["stopApp"].assert_not_called()

    def test_enable_from_running_or_paused_stops_macro(self):
        for state in (1, 2, 4, 6):
            with self.subTest(state=state):
                self.setUp()
                self.ns["run"].value = state
                self.enable()
                self.ns["stopApp"].assert_called_once()
                self.assertEqual(self.ns["run"].value, 3)
                self.assertEqual(self.ns["standbyState"].deadline, 0)
                self.assertIsNone(self.ns["richPresenceManager"])

    def test_disable_stops_only_owned_keep_awake_process(self):
        self.enable()
        self.ns["standbyCommandQueue"].put({"action": "disable"})
        self.tick()
        self.process.terminate.assert_called_once()
        self.process.wait.assert_called_once_with(timeout=2)
        self.assertFalse(self.ns["standbyState"].active)
        self.assertIsNone(self.ns["standbyCaffeinateProc"])
        self.assertEqual(self.ns["run"].value, 3)

    def test_expiration_stops_keep_awake(self):
        self.enable(60)
        self.ns["time"].time.return_value = 1060
        self.tick()
        self.assertFalse(self.ns["standbyState"].active)
        self.assertEqual(self.ns["standbyState"].deadline, 0)
        self.process.terminate.assert_called_once()

    def test_start_request_wakes_normal_supervisor(self):
        self.enable()
        self.ns["run"].value = 1
        self.tick()
        self.assertFalse(self.ns["standbyState"].active)
        self.assertEqual(self.ns["run"].value, 1)
        self.process.terminate.assert_called_once()

    def test_keep_awake_launch_failure_does_not_stop_macro(self):
        self.ns["run"].value = 2
        self.ns["subprocess"].Popen.side_effect = OSError("test launch failure")
        self.enable(60)
        self.assertFalse(self.ns["standbyState"].active)
        self.assertEqual(self.ns["run"].value, 2)
        self.ns["stopApp"].assert_not_called()
        self.ns["appManager"].closeApp.assert_not_called()

    def test_keep_awake_termination_timeout_uses_kill(self):
        self.enable()
        self.process.wait.side_effect = [TimeoutError(), None]
        self.ns["stopStandbyKeepAwake"]()
        self.process.kill.assert_called_once()
        self.assertIsNone(self.ns["standbyCaffeinateProc"])

    def test_stop_request_leaves_macro_fully_stopped(self):
        self.enable()
        # The configured stop hotkey assigns 0 even while already stopped.
        self.ns["run"].value = 0
        self.tick()
        self.assertEqual(self.ns["run"].value, 3,
                         "Stop must not strand standby in a state where Start is rejected")
        self.assertTrue(self.ns["standbyState"].active)
        self.ns["gui"].setRunState.assert_called_with(3)
        self.ns["gui"].toggleStartStop.assert_called_once()
        self.process.terminate.assert_not_called()

    def test_start_after_stop_request_exits_standby(self):
        self.enable()
        self.ns["run"].value = 0
        self.tick()
        self.assertEqual(self.ns["run"].value, 3)
        self.ns["run"].value = 1
        self.tick()
        self.assertFalse(self.ns["standbyState"].active)
        self.assertEqual(self.ns["run"].value, 1)
        self.process.terminate.assert_called_once()

    def test_stop_at_expiration_leaves_macro_fully_stopped(self):
        self.enable(60)
        self.ns["run"].value = 0
        self.ns["time"].time.return_value = 1060
        self.tick()
        self.assertEqual(self.ns["run"].value, 3)
        self.assertFalse(self.ns["standbyState"].active)

    def test_standby_services_eel_greenlets(self):
        try:
            import eel
            import gevent
        except ImportError:
            self.skipTest("Run with the macro venv to check Eel/gevent integration")
        import time
        self.enable()
        self.ns["time"] = time
        self.ns["eel"] = eel
        serviced = []
        task = gevent.spawn(lambda: serviced.append(True))
        try:
            self.tick()
            self.assertTrue(serviced, "Standby starves Eel's gevent event loop")
        finally:
            task.kill()

    def test_eel_callback_can_request_start_during_standby(self):
        try:
            import eel
            import gevent
        except ImportError:
            self.skipTest("Run with the macro venv to check Eel/gevent integration")
        import time
        self.enable()
        self.ns["time"] = time
        self.ns["eel"] = eel
        task = gevent.spawn(setattr, self.ns["run"], "value", 1)
        try:
            self.tick()
            self.assertEqual(self.ns["run"].value, 1)
            self.assertFalse(self.ns["standbyState"].active)
            self.process.terminate.assert_called_once()
        finally:
            task.kill()


if __name__ == "__main__":
    unittest.main()
