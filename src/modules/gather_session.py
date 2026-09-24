"""Gather session pattern execution and failure policy."""

from dataclasses import dataclass
import os
from types import FunctionType


AI_PATTERNS = {"fuzzy_ai_gather", "blooms_ai"}
FALLBACK_PATTERN = "e_lol"


@dataclass(frozen=True)
class PatternCycleResult:
    pattern: str
    fell_back: bool = False
    error: str = ""


class GatherSession:
    """Owns a Gather Session's clock, pattern execution, and cleanup."""

    def __init__(self, pattern_runner, now):
        self.pattern_runner = pattern_runner
        self._now = now
        self._started_at = None
        self._pause_started = None
        self._paused_duration = 0.0
        self._cleanup = []
        self._finished = False

    def start(self, started_at=None):
        self._started_at = self._now() if started_at is None else started_at

    def elapsed(self, paused=False):
        now = self._now()
        if self._started_at is None:
            self.start(now)
        if paused:
            if self._pause_started is None:
                self._pause_started = now
            return self._pause_started - self._started_at - self._paused_duration
        if self._pause_started is not None:
            self._paused_duration += now - self._pause_started
            self._pause_started = None
        return now - self._started_at - self._paused_duration

    def run_cycle(self, namespace, owner=None):
        return self.pattern_runner.run_cycle(namespace, owner)

    def add_cleanup(self, callback):
        if callable(callback):
            self._cleanup.append(callback)

    def finish(self, namespace):
        """Run the pattern's and the session's cleanup once, however the gather ended."""
        if self._finished:
            return
        self._finished = True
        first_error = None
        try:
            self.pattern_runner.finish(namespace)
        except Exception as exc:
            first_error = exc
        for callback in reversed(self._cleanup):
            try:
                callback()
            except Exception as exc:
                if first_error is None:
                    first_error = exc
        if first_error is not None:
            raise first_error


class GatherPatternRunner:
    """Runs one session's selected pattern and owns its permanent fallback."""

    def __init__(self, project_root, selected_pattern, alert, fatal_exceptions=()):
        self._project_root = os.path.abspath(project_root)
        self._patterns_dir = os.path.join(self._project_root, "settings", "patterns")
        self._defaults_dir = os.path.join(self._project_root, "settings", "defaults", "patterns")
        self._alert = alert
        self._fatal_exceptions = fatal_exceptions
        self.selected_pattern = str(selected_pattern)
        self.active_pattern = self.selected_pattern
        self._alerted = False
        self._fallback_active = False
        self._compiled = {}
        self._shipped = {}

    def run_cycle(self, namespace, owner=None):
        """Run one pattern cycle, falling back to e_lol for this session on failure."""
        try:
            self._run(self.active_pattern, namespace)
            error = self._ai_runtime_error(namespace, owner)
            if error:
                raise RuntimeError(error)
            return PatternCycleResult(self.active_pattern)
        except self._fatal_exceptions:
            raise
        except Exception as exc:
            failed_pattern = self.active_pattern
            if failed_pattern == FALLBACK_PATTERN:
                raise
            self._activate_fallback(failed_pattern, exc)
            self._run(FALLBACK_PATTERN, namespace)
            return PatternCycleResult(FALLBACK_PATTERN, True, str(exc))

    def warmup(self, namespace):
        """Run an AI pattern's existing warmup without changing its implementation."""
        try:
            self._run(self.active_pattern, namespace)
            return PatternCycleResult(self.active_pattern)
        except self._fatal_exceptions:
            raise
        except Exception as exc:
            failed_pattern = self.active_pattern
            self._activate_fallback(failed_pattern, exc)
            return PatternCycleResult(FALLBACK_PATTERN, True, str(exc))

    def mark_failed(self, error):
        """Record a warmup failure before the first gather cycle."""
        if self.active_pattern != FALLBACK_PATTERN:
            self._activate_fallback(self.active_pattern, error)

    def finish(self, namespace):
        callback = namespace.get("onGatherEnd")
        if callable(callback):
            callback()

    def is_builtin(self, pattern=None):
        """An unchanged shipped movement pattern can use the compiled built-in path."""
        pattern = pattern or self.active_pattern
        if pattern in AI_PATTERNS:
            return False
        installed = self._path(self._patterns_dir, pattern)
        try:
            # The shipped file does not change during a gather, so read it once. The
            # installed file is read every cycle so an edit takes effect right away.
            if pattern not in self._shipped:
                with open(self._path(self._defaults_dir, pattern), "rb") as shipped_file:
                    self._shipped[pattern] = shipped_file.read()
            with open(installed, "rb") as installed_file:
                return installed_file.read() == self._shipped[pattern]
        except OSError:
            return False

    def _run(self, pattern, namespace):
        path = self._path(self._patterns_dir, pattern)
        if self.is_builtin(pattern) or (pattern == FALLBACK_PATTERN and self._fallback_active):
            function = self._compiled.get(pattern)
            if function is None:
                function = self._compile_builtin(pattern, namespace)
                self._compiled[pattern] = function
            function.__globals__.update(namespace)
            function()
            return
        with open(path) as pattern_file:
            exec(compile(pattern_file.read(), path, "exec"), namespace)

    def _compile_builtin(self, pattern, namespace):
        """Compile an unchanged built-in once and expose it as a normal callable."""
        path = self._path(self._defaults_dir, pattern)
        with open(path) as pattern_file:
            code = compile(pattern_file.read(), path, "exec")
        namespace.setdefault("__builtins__", __builtins__)
        return FunctionType(code, namespace, f"run_{pattern.replace(' ', '_')}")

    def _activate_fallback(self, failed_pattern, error):
        self.active_pattern = FALLBACK_PATTERN
        self._fallback_active = True
        if self._alerted:
            return
        self._alerted = True
        self._alert(failed_pattern, str(error))

    def _ai_runtime_error(self, namespace, owner):
        if self.active_pattern not in AI_PATTERNS:
            return ""
        state_names = {
            "fuzzy_ai_gather": ("_FUZZY_AI_GATHER_STATE", "_fuzzy_ai_gather_state"),
            "blooms_ai": ("_BLOOMS_AI_STATE", "_blooms_ai_state"),
        }
        global_name, attribute_name = state_names[self.active_pattern]
        state = namespace.get(global_name)
        if not isinstance(state, dict) and owner is not None:
            state = getattr(owner, attribute_name, {})
        if not isinstance(state, dict) or state.get("ready"):
            return ""
        return str(state.get("error", "") or "")

    @staticmethod
    def _path(directory, pattern):
        name = os.path.basename(str(pattern))
        if name != pattern or name in ("", ".", ".."):
            raise ValueError("invalid pattern name")
        return os.path.join(directory, f"{name}.py")
