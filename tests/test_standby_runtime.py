"""Run production supervisor code with isolated process and app controls."""

import ast
import asyncio
import copy
from pathlib import Path
from queue import Queue
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ast.parse((ROOT / "src/main.py").read_text())
MAIN = next(node for node in SOURCE.body if isinstance(node, ast.If) and
            isinstance(node.test, ast.Compare) and
            isinstance(node.test.left, ast.Name) and node.test.left.id == "__name__")
FUNCTION_NAMES = {
    "startStandbyKeepAwake", "stopStandbyKeepAwake", "processStandbyCommands",
    "parseAutoStopHours", "processStreamControlCommands", "supervisorTick",
    "releaseInputsSafely", "stopApp", "onExit", "runRuntime",
}


def load_runtime(namespace):
    # Compile whole production callbacks, without startup imports or automation.
    nodes = [copy.deepcopy(node) for node in MAIN.body if
             isinstance(node, ast.FunctionDef) and node.name in FUNCTION_NAMES]
    module = ast.parse("")
    module.body = nodes
    exec(compile(module, "src/main.py", "exec"), namespace)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.process = Mock()
        self.process.poll.return_value = None
        self.ns = {
            "standbyCommandQueue": Queue(),
            "standbyState": SimpleNamespace(active=False, deadline=0.0),
            "standbyCaffeinateProc": None,
            "run": SimpleNamespace(value=3),
            "status": SimpleNamespace(value="idle_main_menu"),
            "current_time": 1000.0,
            "time": SimpleNamespace(time=Mock(return_value=1000.0), sleep=Mock()),
            "subprocess": SimpleNamespace(Popen=Mock(return_value=self.process), DEVNULL=-3),
            "richPresenceManager": Mock(),
            "gui": Mock(), "logger": Mock(), "appManager": Mock(), "stopApp": Mock(),
        }
        self.ns.update({
            "runtimeClosing": False, "keyboardListener": None,
            "macroProc": None, "discordBotProc": None, "prevDiscordBotToken": None,
            "prevRunState": 3, "autoStopStartTime": None, "autoStopDeadline": None,
            "autoStopHours": 0.0, "gui_settings_cache": {}, "last_gui_settings_load": 0,
            "gui_settings_cache_duration": 1.0, "disconnectCooldownUntil": float("inf"),
            "streamControlQueue": Queue(), "logQueue": Queue(), "recentLogs": [],
            "updateGUI": SimpleNamespace(value=0), "stream": Mock(),
            "keyboardModule": Mock(), "mouse": Mock(),
            "pag": SimpleNamespace(FailSafeException=type("FailSafeException", (Exception,), {})),
            "logModule": Mock(), "settingsManager": Mock(), "traceback": Mock(),
            "multiprocessing": Mock(), "macro": Mock(), "discordBot": Mock(),
            "skipTask": Mock(), "presence": SimpleNamespace(value=""),
            "discordMessageQueue": Queue(), "planterCommandQueue": Queue(),
            "pin_requests": Queue(), "skipServer": Mock(), "stopThreads": False,
            "HourlyReport": Mock(), "macroModule": SimpleNamespace(BLENDER_ITEM_SLOTS=1),
            "screenInfo": {"display_type": "test", "screen_width": 100, "screen_height": 100},
        })
        self.ns["settingsManager"].loadAllSettings.return_value = {
            "blender_enable": False, "blender_item_1": "none",
        }
        self.ns["settingsManager"].loadFields.return_value = {}
        self.ns["logModule"].delivery_uses_bot_commands.return_value = False
        self.ns["stream"].streaming = False
        self.ns["gui"].isRecordingKeybind.return_value = False
        self.ns["gui"].isAnyToolRunning.return_value = False
        load_runtime(self.ns)
        self.stop_app = self.ns["stopApp"]
        self.ns["stopApp"] = Mock()

    def tick(self):
        return self.ns["supervisorTick"]()

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
        self.assertEqual(self.ns["run"].value, 2)
        self.ns["multiprocessing"].Process.return_value.start.assert_called_once()
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
        self.assertEqual(self.ns["run"].value, 2)
        self.ns["multiprocessing"].Process.return_value.start.assert_called_once()
        self.process.terminate.assert_called_once()

    def test_stop_at_expiration_leaves_macro_fully_stopped(self):
        self.enable(60)
        self.ns["run"].value = 0
        self.ns["time"].time.return_value = 1060
        self.tick()
        self.assertEqual(self.ns["run"].value, 3)
        self.assertFalse(self.ns["standbyState"].active)

    def test_tick_returns_standby_and_normal_intervals_without_sleep(self):
        self.assertEqual(self.tick(), 0.5)
        self.enable()
        self.assertEqual(self.tick(), 1.0)
        self.ns["standbyCommandQueue"].put({"action": "disable"})
        self.assertEqual(self.tick(), 0.5)
        self.ns["time"].sleep.assert_not_called()

    def test_native_loop_receives_callbacks_and_can_start_between_ticks(self):
        self.enable()
        intervals = []

        def event_loop(tick_callback, close_callback):
            self.assertIs(tick_callback, self.ns["supervisorTick"])
            self.assertIs(close_callback, self.ns["onExit"])
            intervals.append(tick_callback())
            # A native button runs between timer callbacks, without a sleep pump.
            self.ns["run"].value = 1
            intervals.append(tick_callback())
            close_callback()

        self.ns["gui"].runEventLoop.side_effect = event_loop
        self.ns["runRuntime"]()
        self.assertEqual(intervals, [1.0, 0.5])
        self.assertTrue(self.ns["runtimeClosing"])
        self.ns["stopApp"].assert_called_once()
        self.ns["time"].sleep.assert_not_called()

    def test_supervisor_error_exits_and_cleans_up(self):
        self.ns["settingsManager"].loadAllSettings.side_effect = ValueError("test failure")
        self.ns["gui"].runEventLoop.side_effect = lambda tick, close: tick()
        with self.assertRaises(SystemExit) as raised:
            self.ns["runRuntime"]()
        self.assertEqual(raised.exception.code, 1)
        self.ns["traceback"].print_exc.assert_called_once()
        self.ns["stopApp"].assert_called_once()
        self.ns["gui"].stopAllTools.assert_called_once()

    def test_native_loop_return_always_cleans_up(self):
        self.ns["runRuntime"]()
        self.ns["stopApp"].assert_called_once()
        self.assertEqual(self.ns["run"].value, 0)

    def test_close_stops_processes_stream_standby_and_tools_once(self):
        self.enable()
        self.ns["gui"].stopAllTools.reset_mock()
        self.ns["stopApp"] = self.stop_app
        macro_process = Mock()
        self.ns["macroProc"] = macro_process
        self.ns["discordBotProc"] = Mock()
        self.ns["richPresenceManager"] = Mock()
        self.ns["keyboardListener"] = Mock()
        # The fake worker ignores graceful stop, forcing terminate and kill.
        self.ns["time"].time.side_effect = [1000, 1002]
        self.ns["onExit"]()
        self.ns["onExit"]()  # Window close, loop return and atexit share cleanup.
        self.ns["gui"].stopAllTools.assert_called_once()
        self.ns["keyboardListener"].stop.assert_called_once()
        macro_process.terminate.assert_called_once()
        macro_process.kill.assert_called_once()
        self.assertIsNone(self.ns["macroProc"])
        self.ns["stream"].stop.assert_called_once()
        self.ns["discordBotProc"].terminate.assert_called_once()
        self.ns["discordBotProc"].join.assert_called_once()
        self.ns["richPresenceManager"].stop.assert_called_once()
        self.process.terminate.assert_called_once()
        self.assertTrue(self.ns["stopThreads"])
        self.assertFalse(self.ns["standbyState"].active)
        self.assertEqual(self.ns["standbyState"].deadline, 0)
        self.assertEqual(self.ns["run"].value, 0)

    def test_stop_without_worker_preserves_continue_semantics(self):
        self.ns["run"].value = 0
        self.ns["logQueue"].put({"type": "webhook", "time": "now",
                                 "title": "test", "desc": "test", "color": "red"})
        self.assertEqual(self.tick(), 0.5)
        self.assertEqual(self.ns["run"].value, 3)
        self.assertFalse(self.ns["logQueue"].empty())
        self.ns["stopApp"].assert_called_once()

    def test_pause_resume_transitions_keep_shared_state(self):
        self.ns["run"].value = 6
        self.ns["prevRunState"] = 2
        self.tick()
        self.ns["keyboardModule"].releaseMovement.assert_called_once()
        self.ns["mouse"].mouseUp.assert_called_once()
        self.assertEqual(self.ns["prevRunState"], 6)
        self.ns["run"].value = 2
        self.tick()
        self.ns["appManager"].openApp.assert_called_once_with("Roblox")
        self.assertEqual(self.ns["prevRunState"], 2)

    def test_disconnect_and_crash_restart_workers_with_existing_queues(self):
        for state in (2, 4):
            with self.subTest(state=state):
                self.setUp()
                worker = Mock()
                worker.is_alive.return_value = state == 4
                worker.exitcode = 1
                self.ns["macroProc"] = worker
                self.ns["run"].value = state
                self.tick()
                if state == 4:
                    worker.kill.assert_called_once()
                worker.join.assert_called_once()
                self.ns["multiprocessing"].Process.return_value.start.assert_called_once()
                self.assertEqual(self.ns["run"].value, 2)
                args = self.ns["multiprocessing"].Process.call_args[1]["args"]
                self.assertIs(args[2], self.ns["updateGUI"])
                self.assertIs(args[-2], self.ns["planterCommandQueue"])
                self.assertIs(args[-1], self.ns["skipServer"])

    def test_auto_stop_deadline_persists_between_callbacks(self):
        self.ns["settingsManager"].loadAllSettings.return_value["auto_stop_after"] = 1
        self.ns["run"].value = 1
        self.tick()
        self.assertEqual(self.ns["autoStopStartTime"], 1000)
        self.assertEqual(self.ns["autoStopDeadline"], 4600)
        self.ns["time"].time.return_value = 4600
        # This test checks timer cleanup, without generating a real final report.
        self.ns["macroProc"] = None
        self.tick()
        self.assertEqual(self.ns["run"].value, 3)
        self.assertIsNone(self.ns["autoStopDeadline"])
        self.ns["stopApp"].assert_called_once()

    def test_discord_process_persists_and_retains_existing_shared_controls(self):
        self.ns["settingsManager"].loadAllSettings.return_value["discord_bot_token"] = "test"
        self.ns["logModule"].delivery_uses_bot_commands.return_value = True
        self.tick()
        process_factory = self.ns["multiprocessing"].Process
        process_factory.assert_called_once()
        args = process_factory.call_args[1]["args"]
        self.assertIs(args[6], self.ns["updateGUI"])
        self.assertIs(args[-3], self.ns["skipServer"])
        self.assertIs(args[-2], self.ns["standbyCommandQueue"])
        self.assertIs(args[-1], self.ns["standbyState"])
        self.tick()
        process_factory.assert_called_once()
        self.ns["logModule"].delivery_uses_bot_commands.return_value = False
        self.tick()
        process_factory.return_value.terminate.assert_called_once()
        process_factory.return_value.join.assert_called_once()
        self.assertIsNone(self.ns["discordBotProc"])

    def test_gui_update_and_log_queue_are_serviced(self):
        self.ns["updateGUI"].value = 1
        self.ns["logQueue"].put({"type": "webhook", "time": "now",
                                 "title": "test", "desc": "test", "color": "red"})
        self.tick()
        self.ns["gui"].updateGUI.assert_called_once()
        self.assertEqual(self.ns["updateGUI"].value, 0)
        self.ns["gui"].log.assert_called_once_with("now", "test<br>test", "red")
        self.assertEqual(len(self.ns["recentLogs"]), 1)

    def test_hotkeys_read_native_recording_state_on_each_keypress(self):
        hotkeys = next(copy.deepcopy(node) for node in SOURCE.body if
                       isinstance(node, ast.FunctionDef) and node.name == "watch_for_hotkeys")
        module = ast.parse("")
        module.body = [hotkeys]
        exec(compile(module, "src/main.py", "exec"), self.ns)
        callbacks = {}

        def listener_factory(**kwargs):
            callbacks.update(kwargs)
            return Mock()

        self.ns["keyboard"] = SimpleNamespace(Listener=listener_factory)
        self.ns["sys"] = SimpleNamespace(platform="test")
        with patch.dict("sys.modules", {"gui": self.ns["gui"]}):
            start_listener = self.ns["watch_for_hotkeys"](self.ns["run"])
            start_listener()  # Fake listener only; no host input is registered.
            self.ns["gui"].isRecordingKeybind.return_value = True
            callbacks["on_press"]("F1")
            self.assertEqual(self.ns["run"].value, 3)
            self.ns["gui"].isRecordingKeybind.return_value = False
            callbacks["on_press"]("F1")
            self.assertEqual(self.ns["run"].value, 1)
        self.assertEqual(self.ns["gui"].isRecordingKeybind.call_count, 2)


class DiscordRuntimeTests(unittest.TestCase):
    def test_macro_mode_callbacks_use_existing_shared_update_flag(self):
        source = ast.parse((ROOT / "src/modules/discord_bot/discordBot.py").read_text())
        select = next(node for node in ast.walk(source) if
                      isinstance(node, ast.ClassDef) and node.name == "MacroModeSelect")
        callbacks = [next(node for node in select.body if
                          isinstance(node, ast.AsyncFunctionDef) and node.name == "callback"),
                     next(node for node in ast.walk(source) if
                          isinstance(node, ast.AsyncFunctionDef) and node.name == "macro_mode")]
        for callback in callbacks:
            for success in (False, True):
                for update_available in (False, True):
                    with self.subTest(callback=callback.name, success=success,
                                      update_available=update_available):
                        update = SimpleNamespace(value=0) if update_available else None
                        namespace = {
                            "discord": SimpleNamespace(Interaction=object), "updateGUI": update,
                            "update_setting": Mock(return_value=(success, "test")),
                        }

                        async def respond(*args, **kwargs):
                            pass

                        namespace["_update_category_message"] = respond
                        module = ast.parse("")
                        node = copy.deepcopy(callback)
                        node.decorator_list = []
                        module.body = [node]
                        exec(compile(module, "discordBot.py", "exec"), namespace)
                        interaction = SimpleNamespace(response=SimpleNamespace(send_message=respond))
                        if callback.name == "callback":
                            asyncio.run(namespace[callback.name](SimpleNamespace(values=["alt"]), interaction))
                        else:
                            asyncio.run(namespace[callback.name](interaction, "alt"))
                        if update_available:
                            self.assertEqual(update.value, int(success))


if __name__ == "__main__":
    unittest.main()
