"""Test standby without importing screen controls or connecting to Discord."""

import ast
import asyncio
from pathlib import Path
from queue import Queue
import re
from types import SimpleNamespace
from typing import Optional
import unittest
from unittest.mock import Mock


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ast.parse((ROOT / "src/modules/discord_bot/discordBot.py").read_text())


def load_functions(names, namespace):
    # Compile the production functions alone so tests cannot launch the macro.
    nodes = []
    for node in ast.walk(SOURCE):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            node.decorator_list = []
            nodes.append(node)
    module = ast.parse("")
    module.body = nodes
    exec(compile(module, str(ROOT / "src/modules/discord_bot/discordBot.py"), "exec"), namespace)
    return namespace


FUNCTIONS = load_functions(
    {"parse_standby_duration", "format_standby_duration"},
    {"re": re, "Optional": Optional},
)
parse_duration = FUNCTIONS["parse_standby_duration"]
format_duration = FUNCTIONS["format_standby_duration"]


class DurationTests(unittest.TestCase):
    def test_omitted_duration_is_indefinite(self):
        for value in (None, "", " \t\n"):
            with self.subTest(value=value):
                self.assertEqual(parse_duration(value), (None, None))

    def test_complete_durations(self):
        for value, seconds in (
            ("30m", 1800), ("1h 30m", 5400), ("1h30m", 5400),
            (" 2 H \t 3 M ", 7380), ("1d 2h 3m 4s", 93784),
            ("0h 1s", 1), ("00001s", 1), ("1h 1h", 7200),
        ):
            with self.subTest(value=value):
                self.assertEqual(parse_duration(value), (seconds, None))

    def test_rejects_incomplete_or_malformed_durations(self):
        for value in (
            "30m 999", "1h m", "1h 30", "30", "m", "1h 2mm",
            "-1h", "+1h", "1.5h", "30m garbage", "1h,30m", "1e3s", "²h",
        ):
            with self.subTest(value=value):
                seconds, error = parse_duration(value)
                self.assertIsNone(seconds)
                self.assertIn("Use a duration", error)

    def test_zero_is_rejected(self):
        for value in ("0s", "0h 0m"):
            with self.subTest(value=value):
                self.assertEqual(parse_duration(value), (None, "Standby duration must be greater than zero."))

    def test_seven_day_boundary(self):
        for value in ("7d", "168h", "604800s"):
            with self.subTest(value=value):
                self.assertEqual(parse_duration(value), (604800, None))
        for value in ("7d 1s", "604801s", "8d", "999999999999999h", "9" * 5000 + "s"):
            with self.subTest(value=value[:40]):
                self.assertEqual(parse_duration(value), (None, "Standby duration cannot exceed 7 days."))

    def test_long_leading_zeros_are_valid(self):
        self.assertEqual(parse_duration("0" * 5000 + "1s"), (1, None))

    def test_formatting(self):
        for seconds, expected in (
            (None, "until you disable it"), (1, "1 second"),
            (5400, "1 hour 30 minutes"), (93784, "1 day 2 hours 3 minutes 4 seconds"),
        ):
            with self.subTest(seconds=seconds):
                self.assertEqual(format_duration(seconds), expected)


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.queue = Queue()
        self.state = SimpleNamespace(active=False)
        self.send = Mock()

        async def send_message(*args, **kwargs):
            self.send(*args, **kwargs)

        self.interaction = SimpleNamespace(response=SimpleNamespace(send_message=send_message))
        self.namespace = load_functions({"standby"}, dict(
            FUNCTIONS, discord=SimpleNamespace(Interaction=object),
            standby_command_queue=self.queue, standby_state=self.state,
        ))

    def invoke(self, duration=None):
        asyncio.run(self.namespace["standby"](self.interaction, duration))

    def test_valid_duration_queues_enable(self):
        self.invoke("1h 30m")
        self.assertEqual(self.queue.get_nowait(), {"action": "enable", "duration_seconds": 5400})
        self.assertIn("1 hour 30 minutes", self.send.call_args[0][0])

    def test_omitted_duration_queues_indefinite_standby(self):
        self.invoke()
        self.assertEqual(self.queue.get_nowait(), {"action": "enable", "duration_seconds": None})

    def test_invalid_duration_does_not_queue_command(self):
        self.invoke("30m 999")
        self.assertTrue(self.queue.empty())
        self.assertTrue(self.send.call_args[1]["ephemeral"])

    def test_repeated_command_disables_standby(self):
        self.state.active = True
        self.invoke()
        self.assertEqual(self.queue.get_nowait(), {"action": "disable"})

    def test_unavailable_standby_does_not_queue_command(self):
        self.namespace["standby_state"] = None
        self.invoke("30m")
        self.assertTrue(self.queue.empty())
        self.assertIn("unavailable", self.send.call_args[0][0])

    def test_help_lists_standby_for_modern_and_legacy_commands(self):
        for legacy in (False, True):
            with self.subTest(legacy=legacy):
                class Embed:
                    def __init__(self, **kwargs):
                        self.fields = []

                    def add_field(self, **kwargs):
                        self.fields.append(SimpleNamespace(**kwargs))

                    def set_field_at(self, index, **kwargs):
                        self.fields[index] = SimpleNamespace(**kwargs)

                namespace = load_functions({"help_command"}, {
                    "discord": SimpleNamespace(Interaction=object, Embed=Embed),
                    "legacyCommands": SimpleNamespace(IS_LEGACY=legacy, PREFIX="fuzz!"),
                    "TAD_ALT_SYNC_HELP_TEXT": "Alt sync help",
                    "DISCORD_COMMAND_PERMISSION_CATEGORIES": {},
                })
                asyncio.run(namespace["help_command"](self.interaction))
                embed = self.send.call_args[1]["embed"]
                prefix = "fuzz!" if legacy else "/"
                self.assertIn("`" + prefix + "standby [duration]`", embed.fields[0].value)
                self.assertTrue(all(len(field.value) <= 1024 for field in embed.fields))


if __name__ == "__main__":
    unittest.main()
