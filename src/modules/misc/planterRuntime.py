"""Persistent active macro runtime used by special planter routes."""

import json
import math
import os
import time


class PlanterRuntimeClock:
    def __init__(self, path, shared, clock=time.monotonic):
        self.path = path
        self.shared = shared
        self.clock = clock
        try:
            with open(path) as handle:
                value = float(json.load(handle)['seconds'])
            shared.value = value if math.isfinite(value) and value >= 0 else 0.0
        except (OSError, ValueError, TypeError, KeyError):
            shared.value = 0.0
        self.previous = clock()
        self.last_saved = self.previous
        self.saved_value = shared.value
        self.active = False

    def tick(self, active):
        now = self.clock()
        # Require both samples to be active; transitions never credit stopped time.
        if self.active and active:
            self.shared.value += max(0.0, now - self.previous)
        stopped = self.active and not active
        self.previous = now
        self.active = active
        if stopped or (self.shared.value != self.saved_value and now - self.last_saved >= 5):
            self.save()

    def save(self):
        temporary = self.path + '.tmp'
        with open(temporary, 'w') as handle:
            json.dump({'seconds': self.shared.value}, handle)
        os.replace(temporary, self.path)
        self.last_saved = self.clock()
        self.saved_value = self.shared.value


def normalize_route_runtime(planter, runtime):
    if not planter.get('special_drop_id'):
        return
    if planter.get('runtime_baseline') is None:
        # Old wall timestamps cannot prove how much macro runtime elapsed.
        planter['runtime_baseline'] = runtime
        planter['growth_runtime'] = 0.0
    planter['placed_time'] = 0
    planter['harvest_time'] = 0


def route_growth(planter, runtime):
    baseline = planter.get('runtime_baseline')
    if baseline is None:
        return 0.0
    return max(0.0, planter.get('growth_runtime', 0.0)) + max(0.0, runtime - baseline)


def route_remaining(planter, runtime):
    return max(0.0, planter.get('natural_grow_duration', 0.0) - route_growth(planter, runtime))
