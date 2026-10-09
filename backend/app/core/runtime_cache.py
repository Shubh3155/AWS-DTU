"""Bounded per-process read cache; expiry never falls back to an older value."""

from collections import OrderedDict
from copy import deepcopy
from threading import Lock
from time import monotonic


class RuntimeCache:
    def __init__(self, capacity=32, clock=monotonic):
        self.capacity = capacity
        self.clock = clock
        self.values = OrderedDict()
        self.lock = Lock()

    def get(self, key):
        with self.lock:
            item = self.values.get(key)
            if item is None:
                return None
            deadline, value = item
            if self.clock() >= deadline:
                del self.values[key]
                return None
            self.values.move_to_end(key)
            return deepcopy(value)

    def put(self, key, value, ttl):
        if value is None or ttl <= 0:
            return
        with self.lock:
            self.values[key] = (self.clock() + ttl, deepcopy(value))
            self.values.move_to_end(key)
            while len(self.values) > self.capacity:
                self.values.popitem(last=False)
