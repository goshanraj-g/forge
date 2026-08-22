"""In-memory storage for active factory simulations"""

from backend.simulator.engine import FactorySimulator
from backend.simulator.seed import load_factory


class FactoryStore:
    def __init__(self) -> None:
        self._simulators: dict[str, FactorySimulator] = {}

    def get(self, name: str) -> FactorySimulator:
        if name not in self._simulators:
            state = load_factory(name)
            self._simulators[name] = FactorySimulator(state)

        return self._simulators[name]

    def reset(self, name: str) -> FactorySimulator:
        simulator = FactorySimulator(load_factory(name))
        self._simulators[name] = simulator
        return simulator

    def clear(self) -> None:
        self._simulators.clear()


factory_store = FactoryStore()
