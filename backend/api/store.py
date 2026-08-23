"""In-memory storage for active factory simulations."""

from collections.abc import Iterator
from contextlib import contextmanager
from threading import RLock

from backend.simulator.engine import FactorySimulator
from backend.simulator.seed import load_factory


class FactoryStore:
    def __init__(self) -> None:
        self._simulators: dict[str, FactorySimulator] = {}
        self._locks: dict[str, RLock] = {}
        self._registry_lock = RLock()

    def get(self, name: str) -> FactorySimulator:
        """Return the active simulator, lazily activating a known factory."""
        with self._registry_lock:
            if name not in self._simulators:
                state = load_factory(name)
                self._simulators[name] = FactorySimulator(state)
                self._locks[name] = RLock()

            return self._simulators[name]

    def reset(self, name: str) -> FactorySimulator:
        with self._registry_lock:
            simulator = FactorySimulator(load_factory(name))
            self._simulators[name] = simulator
            self._locks.setdefault(name, RLock())
            return simulator

    def clear(self) -> None:
        with self._registry_lock:
            self._simulators.clear()
            self._locks.clear()

    @contextmanager
    def locked(self, name: str) -> Iterator[FactorySimulator]:
        simulator = self.get(name)
        with self._registry_lock:
            lock = self._locks[name]
        with lock:
            yield simulator


factory_store = FactoryStore()
