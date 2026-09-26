"""Gather session pattern execution and failure policy."""

import os


AI_PATTERNS = {"fuzzy_ai_gather", "blooms_ai"}
FALLBACK_PATTERN = "e_lol"


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

    def run_cycle(self, namespace, owner=None):
        """Run one pattern cycle, falling back to e_lol for this session on failure.
        Returns the pattern that ran."""
        try:
            self._run(self.active_pattern, namespace)
            error = self._ai_runtime_error(namespace, owner)
            if error:
                raise RuntimeError(error)
        except self._fatal_exceptions:
            raise
        except Exception as exc:
            if self.active_pattern == FALLBACK_PATTERN:
                raise
            self._activate_fallback(self.active_pattern, exc)
            self._run(FALLBACK_PATTERN, namespace)
        return self.active_pattern

    def warmup(self, namespace):
        """Run an AI pattern's existing warmup without changing its implementation.
        Returns the pattern the gather should use."""
        try:
            self._run(self.active_pattern, namespace)
        except self._fatal_exceptions:
            raise
        except Exception as exc:
            self._activate_fallback(self.active_pattern, exc)
        return self.active_pattern

    def mark_failed(self, error):
        """Record a warmup failure before the first gather cycle."""
        if self.active_pattern != FALLBACK_PATTERN:
            self._activate_fallback(self.active_pattern, error)

    def finish(self, namespace):
        callback = namespace.get("onGatherEnd")
        if callable(callback):
            callback()

    def _run(self, pattern, namespace):
        # the fallback runs the shipped e_lol, so a broken edit of e_lol can't break it too
        directory = self._defaults_dir if pattern == FALLBACK_PATTERN and self._fallback_active else self._patterns_dir
        path = self._path(directory, pattern)
        with open(path) as pattern_file:
            exec(compile(pattern_file.read(), path, "exec"), namespace)

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
